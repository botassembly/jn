#!/usr/bin/env -S uv run --script
"""Filter NDJSON streams using jq expressions."""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = []  # jq doesn't match files, invoked explicitly via 'jn filter'
# ///

import sys
import json
import subprocess
import shutil
from typing import Iterator, Optional


def filters(config: Optional[dict] = None) -> Iterator[dict]:
    """Filter NDJSON stream using jq expression.

    Reads NDJSON from stdin, applies jq filter, outputs NDJSON.
    Streams line-by-line with automatic backpressure.

    Config:
        query: jq expression (default: '.')

    Yields:
        Filtered/transformed records as dicts
    """
    if config is None:
        config = {}

    query = config.get('query', '.')

    # Check if jq is available
    if not shutil.which('jq'):
        print("Error: jq command not found. Install from: https://jqlang.github.io/jq/", file=sys.stderr)
        sys.exit(1)

    # Stream through jq using Popen (automatic backpressure via OS pipes)
    try:
        # Check if stdin is a real file (production) or StringIO (test)
        try:
            sys.stdin.fileno()
            stdin_source = sys.stdin
            input_data = None
        except (AttributeError, OSError):
            # Test environment - read and pipe
            stdin_source = subprocess.PIPE
            input_data = sys.stdin.read()

        jq_process = subprocess.Popen(
            ['jq', '-c', query],  # -c for compact output (NDJSON)
            stdin=stdin_source,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # If test mode, write input to jq's stdin
        if input_data is not None:
            jq_process.stdin.write(input_data)
            jq_process.stdin.close()

        # Stream output line by line
        for line in jq_process.stdout:
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
                # JQ might return primitives (strings, numbers, arrays)
                # Wrap non-dict values in object for NDJSON compatibility
                if isinstance(record, dict):
                    yield record
                elif isinstance(record, list):
                    # If array, yield each element
                    for item in record:
                        if isinstance(item, dict):
                            yield item
                        else:
                            yield {'value': item}
                else:
                    # Primitive value - wrap it
                    yield {'value': record}
            except json.JSONDecodeError:
                # Invalid JSON output from jq - wrap as string
                yield {'value': line}

        # Wait for process to complete
        jq_process.wait()

        # Check for errors
        if jq_process.returncode != 0:
            stderr_data = jq_process.stderr.read()
            print(f"jq error: {stderr_data}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        # Clean up process if still running
        try:
            jq_process.kill()
        except:
            pass
        print(f"jq error: {e}", file=sys.stderr)
        sys.exit(1)


def test() -> bool:
    """Run self-tests with real jq (no mocks).

    Returns:
        True if all tests pass
    """
    # Check if jq is available
    if not shutil.which('jq'):
        print("⚠ jq not installed, skipping tests", file=sys.stderr)
        print("  Install from: https://jqlang.github.io/jq/", file=sys.stderr)
        return True  # Don't fail if jq not installed

    from io import StringIO

    print("Testing jq filter plugin...", file=sys.stderr)

    # Test 1: Select field
    sys.stdin = StringIO('{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n')
    results = list(filters({'query': '.name'}))
    expected = [{"value": "Alice"}, {"value": "Bob"}]

    if results == expected:
        print("✓ jq field select test passed", file=sys.stderr)
    else:
        print(f"✗ jq test failed: {results}", file=sys.stderr)
        return False

    # Test 2: Filter by condition
    sys.stdin = StringIO('{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n')
    results = list(filters({'query': 'select(.age > 25)'}))
    expected = [{"name": "Alice", "age": 30}]

    if results == expected:
        print("✓ jq filter condition test passed", file=sys.stderr)
    else:
        print(f"✗ jq filter test failed: {results}", file=sys.stderr)
        return False

    # Test 3: Transform object
    sys.stdin = StringIO('{"name":"Alice","age":30}\n')
    results = list(filters({'query': '{user: .name, years: .age}'}))
    expected = [{"user": "Alice", "years": 30}]

    if results == expected:
        print("✓ jq transform test passed", file=sys.stderr)
    else:
        print(f"✗ jq transform test failed: {results}", file=sys.stderr)
        return False

    print("All jq tests passed!", file=sys.stderr)
    return True


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='jq filter plugin - transform NDJSON streams')
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run self-tests'
    )
    parser.add_argument(
        '--query', '-q',
        default='.',
        help='jq query expression (default: .)'
    )

    args = parser.parse_args()

    if args.test:
        success = test()
        sys.exit(0 if success else 1)

    # Run filter
    config = {'query': args.query}
    for record in filters(config):
        print(json.dumps(record), flush=True)
