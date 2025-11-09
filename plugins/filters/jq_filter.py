#!/usr/bin/env python3
"""JQ filter plugin - Transform JSON data using jq expressions.

Wraps the jq command-line tool to filter and transform NDJSON streams.
Requires jq to be installed on the system.
"""
# /// script
# dependencies = []
# ///
# META: type=filter, streaming=true

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


def examples() -> list[dict]:
    """Return example usage patterns.

    Returns:
        List of example dicts with input, query, and expected output
    """
    return [
        {
            "description": "Select field",
            "query": ".name",
            "input": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ],
            "expected": [
                "Alice",  # jq returns strings directly
                "Bob"
            ]
        },
        {
            "description": "Filter by condition",
            "query": "select(.age > 25)",
            "input": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ],
            "expected": [
                {"name": "Alice", "age": 30}
            ]
        },
        {
            "description": "Transform object",
            "query": "{user: .name, years: .age}",
            "input": [
                {"name": "Alice", "age": 30}
            ],
            "expected": [
                {"user": "Alice", "years": 30}
            ]
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
        query = example['query']
        input_data = example['input']
        expected = example['expected']

        try:
            # Setup stdin with NDJSON input
            input_lines = [json.dumps(record) for record in input_data]
            sys.stdin = StringIO('\n'.join(input_lines))

            # Run filter
            results = list(run({'query': query}))

            # Compare (note: for simple value extracts, we wrap in {'value': x})
            if results == expected:
                print(f"✓ {desc}", file=sys.stderr)
                passed += 1
            else:
                print(f"✗ {desc}: Output mismatch", file=sys.stderr)
                print(f"  Query: {query}", file=sys.stderr)
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

    args = parser.parse_args()

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
