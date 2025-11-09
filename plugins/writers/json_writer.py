#!/usr/bin/env python3
"""JSON writer plugin - Convert NDJSON to JSON array.

Reads NDJSON from stdin and outputs a proper JSON array.
Supports pretty-printing and compact output.
"""
# /// script
# dependencies = []
# ///
# META: type=target, handles=[".json"]

import sys
import json
from typing import Optional


def run(config: Optional[dict] = None) -> None:
    """Convert NDJSON stream to JSON array.

    Reads NDJSON from stdin, collects all records, outputs JSON array.

    Args:
        config: Configuration dict
            - pretty: bool - Enable pretty-printing (default: True)
            - indent: int - Indentation spaces (default: 2)
            - output: str - Output file path (default: stdout)
    """
    if config is None:
        config = {}

    pretty = config.get('pretty', True)
    indent = config.get('indent', 2) if pretty else None
    output_path = config.get('output')

    # Collect all records
    records = []
    for line in sys.stdin:
        line = line.strip()
        if line:
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse line: {e}", file=sys.stderr)
                continue

    # Output as JSON array
    json_output = json.dumps(records, indent=indent, ensure_ascii=False)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(json_output)
            f.write('\n')
    else:
        print(json_output)


def examples() -> list[dict]:
    """Return example usage patterns.

    Returns:
        List of example dicts with input and expected output
    """
    return [
        {
            "description": "Basic NDJSON to JSON",
            "config": {"pretty": False},
            "input": '{"name": "Alice", "age": 30}\n{"name": "Bob", "age": 25}\n',
            "expected": '[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]'
        },
        {
            "description": "Pretty-printed output",
            "config": {"pretty": True, "indent": 2},
            "input": '{"name": "Alice"}\n{"name": "Bob"}\n',
            "expected": """[
  {
    "name": "Alice"
  },
  {
    "name": "Bob"
  }
]"""
        },
        {
            "description": "Empty input",
            "config": {"pretty": False},
            "input": "",
            "expected": "[]"
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

    for example in examples():
        desc = example['description']
        config = example.get('config', {})
        input_data = example['input']
        expected = example['expected'].strip()

        try:
            # Setup stdin
            sys.stdin = StringIO(input_data)

            # Capture stdout
            original_stdout = sys.stdout
            sys.stdout = StringIO()

            # Run writer
            run(config)

            # Get output
            output = sys.stdout.getvalue().strip()
            sys.stdout = original_stdout

            # Compare
            if output == expected:
                print(f"✓ {desc}", file=sys.stderr)
                passed += 1
            else:
                print(f"✗ {desc}: Output mismatch", file=sys.stderr)
                print(f"  Expected: {repr(expected)}", file=sys.stderr)
                print(f"  Got: {repr(output)}", file=sys.stderr)
                failed += 1

        except Exception as e:
            sys.stdout = original_stdout
            print(f"✗ {desc}: {e}", file=sys.stderr)
            failed += 1

    total = passed + failed
    print(f"\n{passed}/{total} tests passed", file=sys.stderr)

    return failed == 0


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Convert NDJSON to JSON array'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output file (default: stdout)'
    )
    parser.add_argument(
        '--pretty', '-p',
        action='store_true',
        default=True,
        help='Pretty-print output (default: true)'
    )
    parser.add_argument(
        '--compact', '-c',
        action='store_true',
        help='Compact output (no indentation)'
    )
    parser.add_argument(
        '--indent',
        type=int,
        default=2,
        help='Indentation spaces (default: 2)'
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

    # Build config
    config = {
        'pretty': not args.compact if args.compact else args.pretty,
        'indent': args.indent,
    }

    if args.output:
        config['output'] = args.output

    # Run writer
    run(config)
