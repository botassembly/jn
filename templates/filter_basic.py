#!/usr/bin/env python3
"""{{DESCRIPTION}}

{{LONG_DESCRIPTION}}
"""
# /// script
# dependencies = [{{DEPENDENCIES}}]
# ///
# META: type=filter, streaming=true

import sys
import json
import argparse
from typing import Iterator, Optional


def run(config: Optional[dict] = None) -> Iterator[dict]:
    """{{RUN_DESCRIPTION}}

    Config keys:
        {{CONFIG_KEYS}}

    Yields:
        Filtered/transformed records
    """
    config = config or {}

    # TODO: Implement your filter logic here
    # Read NDJSON from stdin, transform, and yield

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            record = json.loads(line)

            # Apply your transformation here
            # Example: Add a field
            record['processed'] = True

            yield record

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}", file=sys.stderr)
            continue


def examples() -> list[dict]:
    """Return test cases for this plugin.

    Each example includes:
        - description: What this example demonstrates
        - input: Sample NDJSON input
        - expected: Expected output records
    """
    return [
        {
            "description": "Basic filtering example",
            "input": '{"value": 10}\n{"value": 20}\n',
            "expected": [
                {"value": 10, "processed": True},
                {"value": 20, "processed": True}
            ]
        }
    ]


def test() -> bool:
    """Run built-in tests.

    Returns:
        True if all tests pass
    """
    from io import StringIO

    passed = 0
    failed = 0
    test_cases = examples()

    for i, test_case in enumerate(test_cases, 1):
        desc = test_case['description']
        test_input = test_case['input']
        expected = test_case['expected']

        # Mock stdin
        old_stdin = sys.stdin
        sys.stdin = StringIO(test_input)

        try:
            # Run plugin with test config
            config = test_case.get('config', {})
            results = list(run(config))

            # Compare results
            if results == expected:
                print(f"✓ Test {i}: {desc}", file=sys.stderr)
                passed += 1
            else:
                print(f"✗ Test {i}: {desc}", file=sys.stderr)
                print(f"  Expected: {expected}", file=sys.stderr)
                print(f"  Got: {results}", file=sys.stderr)
                failed += 1

        except Exception as e:
            print(f"✗ Test {i}: {desc} - {e}", file=sys.stderr)
            failed += 1
        finally:
            sys.stdin = old_stdin

    # Summary
    print(f"\n{passed} passed, {failed} failed", file=sys.stderr)
    return failed == 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='{{DESCRIPTION}}')
    parser.add_argument('--examples', action='store_true', help='Show usage examples')
    parser.add_argument('--test', action='store_true', help='Run built-in tests')

    args = parser.parse_args()

    if args.examples:
        print(json.dumps(examples(), indent=2))
    elif args.test:
        success = test()
        sys.exit(0 if success else 1)
    else:
        # Run normal operation
        for record in run():
            print(json.dumps(record))
