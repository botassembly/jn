#!/usr/bin/env python3
"""JQ filter plugin - Transform JSON data using jq expressions.

Wraps the jq command-line tool to filter and transform NDJSON streams.
Requires jq to be installed on the system.
"""
# /// script
# dependencies = []
# ///
# META: type=filter, streaming=true
# KEYWORDS: jq, filter, transform, query, json
# DESCRIPTION: Transform JSON data using jq expressions

import sys
import json
import subprocess
import shutil
from typing import Optional, Iterator


def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Filter NDJSON stream using jq expression.

    Reads NDJSON from stdin, applies jq filter, outputs NDJSON.

    Args:
        config: Configuration dict with 'query' key containing jq expression

    Yields:
        Filtered/transformed records as dicts
    """
    if config is None:
        config = {}

    query = config.get('query', '.')

    # Check if jq is available
    if not shutil.which('jq'):
        print("Error: jq command not found. Please install jq.", file=sys.stderr)
        sys.exit(1)

    # Read all input as NDJSON
    input_lines = []
    for line in sys.stdin:
        line = line.strip()
        if line:
            input_lines.append(line)

    if not input_lines:
        return

    # Process with jq
    # We pass NDJSON input and get NDJSON output using -c flag
    try:
        # Join input lines with newlines
        input_data = '\n'.join(input_lines)

        # Run jq with -c for compact output (NDJSON)
        result = subprocess.run(
            ['jq', '-c', query],
            input=input_data,
            capture_output=True,
            text=True,
            check=True
        )

        # Parse output as NDJSON
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    record = json.loads(line)
                    yield record
                except json.JSONDecodeError:
                    # If jq returns non-JSON (like strings or numbers), wrap it
                    yield {'value': line}

    except subprocess.CalledProcessError as e:
        print(f"jq error: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def schema() -> dict:
    """Return JSON schema for jq filter output.

    JQ filter can output any JSON structure depending on the query.
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "description": "JSON object transformed by jq expression"
    }


def examples() -> list[dict]:
    """Return example usage patterns.

    Returns:
        List of example dicts with input, query, and expected output
    """
    return [
        {
            "description": "Select field",
            "config": {"query": ".name"},
            "input": '{"name": "Alice", "age": 30}\n{"name": "Bob", "age": 25}\n',
            "expected": [
                {"value": "Alice"},  # Wrapped non-dict values
                {"value": "Bob"}
            ],
            "ignore_fields": set()  # Deterministic output
        },
        {
            "description": "Filter by condition",
            "config": {"query": "select(.age > 25)"},
            "input": '{"name": "Alice", "age": 30}\n{"name": "Bob", "age": 25}\n',
            "expected": [
                {"name": "Alice", "age": 30}
            ],
            "ignore_fields": set()
        },
        {
            "description": "Transform object",
            "config": {"query": "{user: .name, years: .age}"},
            "input": '{"name": "Alice", "age": 30}\n',
            "expected": [
                {"user": "Alice", "years": 30}
            ],
            "ignore_fields": set()
        }
    ]


def test() -> bool:
    """Run built-in tests.

    Returns:
        True if all tests pass
    """
    # Check if jq is available
    if not shutil.which('jq'):
        print("✗ jq not installed, skipping tests", file=sys.stderr)
        return False

    from io import StringIO

    passed = 0
    failed = 0

    for example in examples():
        desc = example['description']
        config = example.get('config', {})
        test_input = example['input']
        expected = example['expected']

        try:
            # Setup stdin with NDJSON input
            old_stdin = sys.stdin
            sys.stdin = StringIO(test_input)

            # Run filter
            results = list(run(config))
            sys.stdin = old_stdin

            # Compare
            if results == expected:
                print(f"✓ {desc}", file=sys.stderr)
                passed += 1
            else:
                print(f"✗ {desc}: Output mismatch", file=sys.stderr)
                print(f"  Expected: {expected}", file=sys.stderr)
                print(f"  Got: {results}", file=sys.stderr)
                failed += 1

        except Exception as e:
            sys.stdin = old_stdin
            print(f"✗ {desc}: {e}", file=sys.stderr)
            failed += 1

    total = passed + failed
    print(f"\n{passed}/{total} tests passed", file=sys.stderr)

    return failed == 0


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Filter NDJSON using jq expressions'
    )
    parser.add_argument(
        '--query', '-q',
        default='.',
        help='JQ query expression (default: .)'
    )
    parser.add_argument(
        '--examples',
        action='store_true',
        help='Show usage examples'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run built-in tests'
    )
    parser.add_argument(
        '--schema',
        action='store_true',
        help='Output JSON schema'
    )

    args = parser.parse_args()

    if args.schema:
        print(json.dumps(schema(), indent=2))
        sys.exit(0)

    if args.examples:
        print(json.dumps(examples(), indent=2))
        sys.exit(0)

    if args.test:
        success = test()
        sys.exit(0 if success else 1)

    # Run filter
    config = {'query': args.query}
    for record in run(config):
        print(json.dumps(record))
