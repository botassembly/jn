#!/usr/bin/env python3
"""Write NDJSON to YAML format.

Converts JSON Lines stream to YAML output.
Can produce single document or multi-document streams.
"""
# /// script
# dependencies = ["PyYAML>=6.0"]
# ///
# META: type=target, handles=[".yaml", ".yml"]

import sys
import json
import argparse
from typing import Optional


def run(config: Optional[dict] = None) -> None:
    """Convert NDJSON stream to YAML.

    Config keys:
        multi_document: Output as multi-document stream (default: False)
        indent: Indentation spaces (default: 2)
        explicit_start: Add explicit document start marker (default: False)

    Reads NDJSON from stdin, writes YAML to stdout.
    """
    import yaml

    config = config or {}
    multi_document = config.get('multi_document', False)
    indent = config.get('indent', 2)
    explicit_start = config.get('explicit_start', False)

    # Read all records
    records = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))

    if not records:
        return

    # Output YAML
    if multi_document:
        # Output each record as a separate document
        for i, record in enumerate(records):
            if i > 0 or explicit_start:
                print("---")
            yaml.dump(record, sys.stdout, default_flow_style=False, indent=indent, allow_unicode=True)
    else:
        # Output single document (list of records)
        if explicit_start:
            print("---")
        yaml.dump(records, sys.stdout, default_flow_style=False, indent=indent, allow_unicode=True)


def examples() -> list[dict]:
    """Return test cases for this plugin.

    Each example includes:
        - description: What this example demonstrates
        - input: Sample NDJSON input
        - expected_pattern: Pattern to check in output
    """
    return [
        {
            "description": "Single document output (list)",
            "input": '{"name": "Alice", "age": 30}\n{"name": "Bob", "age": 25}\n',
            "config": {"multi_document": False},
            "expected_pattern": "- age: 30\n  name: Alice\n- age: 25\n  name: Bob"
        },
        {
            "description": "Multi-document output",
            "input": '{"name": "Alice"}\n{"name": "Bob"}\n',
            "config": {"multi_document": True},
            "expected_pattern": "---"
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
    parser = argparse.ArgumentParser(description='Write NDJSON to YAML format')
    parser.add_argument('--multi-document', action='store_true',
                        help='Output as multi-document stream')
    parser.add_argument('--indent', type=int, default=2,
                        help='Indentation spaces (default: 2)')
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
        config = {
            'multi_document': args.multi_document,
            'indent': args.indent
        }
        run(config)
