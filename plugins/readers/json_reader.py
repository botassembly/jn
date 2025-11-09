#!/usr/bin/env python3
"""Read JSON/NDJSON and pass through as NDJSON.

For JSON arrays, each element becomes a NDJSON line.
For single JSON objects, output as-is.
For NDJSON (already line-delimited), pass through unchanged.
"""
# /// script
# dependencies = []
# ///
# META: type=source, handles=[".json", ".jsonl", ".ndjson"], streaming=true

import json
import sys
from typing import Iterator, Optional


def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Read JSON from stdin, emit NDJSON.

    Handles three cases:
    1. NDJSON input (one JSON object per line) - passthrough
    2. JSON array - emit each element as NDJSON line
    3. Single JSON object - emit as NDJSON line

    Config keys:
        None currently

    Yields:
        Dict per JSON object
    """
    config = config or {}

    # Try to read as NDJSON first (streaming)
    content = sys.stdin.read()

    if not content.strip():
        return

    # Try as NDJSON (line-delimited)
    lines = content.strip().split('\n')
    if len(lines) > 1:
        # Multiple lines - assume NDJSON
        for line in lines:
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    # Not NDJSON, fall through to full parse
                    break
        else:
            # Successfully parsed all lines as NDJSON
            return

    # Parse as complete JSON (array or object)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # If array, emit each element
    if isinstance(data, list):
        for item in data:
            yield item
    else:
        # Single object
        yield data


def examples() -> list[dict]:
    """Return test cases."""
    return [
        {
            "description": "NDJSON passthrough",
            "input": '{"name": "Alice"}\n{"name": "Bob"}\n',
            "expected": [
                {"name": "Alice"},
                {"name": "Bob"}
            ]
        },
        {
            "description": "JSON array",
            "input": '[{"name": "Alice"}, {"name": "Bob"}]',
            "expected": [
                {"name": "Alice"},
                {"name": "Bob"}
            ]
        },
        {
            "description": "Single JSON object",
            "input": '{"name": "Alice", "age": 30}',
            "expected": [
                {"name": "Alice", "age": 30}
            ]
        }
    ]


def test() -> bool:
    """Run built-in tests."""
    from io import StringIO

    passed = 0
    failed = 0

    for example in examples():
        desc = example['description']
        try:
            sys.stdin = StringIO(example['input'])
            results = list(run())

            expected = example['expected']
            if results == expected:
                print(f"✓ {desc}", file=sys.stderr)
                passed += 1
            else:
                print(f"✗ {desc}: Output mismatch", file=sys.stderr)
                print(f"  Expected: {expected}", file=sys.stderr)
                print(f"  Got: {results}", file=sys.stderr)
                failed += 1

        except Exception as e:
            print(f"✗ {desc}: {e}", file=sys.stderr)
            failed += 1

    total = passed + failed
    print(f"\n{passed}/{total} tests passed", file=sys.stderr)
    return failed == 0


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Read JSON/NDJSON and output NDJSON'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run built-in tests'
    )

    args = parser.parse_args()

    if args.test:
        success = test()
        sys.exit(0 if success else 1)
    else:
        for record in run():
            print(json.dumps(record), flush=True)
