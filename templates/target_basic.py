#!/usr/bin/env python3
"""{{DESCRIPTION}}

{{LONG_DESCRIPTION}}
"""
# /// script
# dependencies = [{{DEPENDENCIES}}]
# ///
# META: type=target, handles=[{{HANDLES}}]

import sys
import json
import argparse
from typing import Optional


def run(config: Optional[dict] = None) -> None:
    """{{RUN_DESCRIPTION}}

    Config keys:
        {{CONFIG_KEYS}}

    Reads NDJSON from stdin, writes to stdout or file.
    """
    config = config or {}

    # Read all records
    records = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}", file=sys.stderr)
            continue

    if not records:
        return

    # TODO: Implement your output format here
    # Example: Simple JSON array output
    output = json.dumps(records, indent=2)
    print(output)


def examples() -> list[dict]:
    """Return test cases for this plugin.

    Each example includes:
        - description: What this example demonstrates
        - input: Sample NDJSON input
        - expected_pattern: Pattern to check in output
    """
    return [
        {
            "description": "Basic output example",
            "input": '{"name": "Alice"}\n{"name": "Bob"}\n',
            "expected_pattern": "Alice"
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
        expected_pattern = test_case.get('expected_pattern', '')

        # Mock stdin/stdout
        old_stdin = sys.stdin
        old_stdout = sys.stdout
        sys.stdin = StringIO(test_input)
        sys.stdout = StringIO()

        try:
            # Run plugin with test config
            config = test_case.get('config', {})
            run(config)

            # Get output
            output = sys.stdout.getvalue()

            # Check for expected pattern
            if expected_pattern in output:
                print(f"✓ Test {i}: {desc}", file=sys.stderr)
                passed += 1
            else:
                print(f"✗ Test {i}: {desc}", file=sys.stderr)
                print(f"  Expected pattern: {expected_pattern}", file=sys.stderr)
                print(f"  Got output:\n{output}", file=sys.stderr)
                failed += 1

        except Exception as e:
            print(f"✗ Test {i}: {desc} - {e}", file=sys.stderr)
            failed += 1
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout

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
        run()
