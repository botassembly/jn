#!/usr/bin/env python3
"""Write NDJSON to XML format.

Converts JSON Lines stream to XML output.
"""
# /// script
# dependencies = ["xmltodict>=0.13.0"]
# ///
# META: type=target, handles=[".xml"]
# KEYWORDS: xml, writer, output, markup
# DESCRIPTION: Write NDJSON to XML format

import sys
import json
import argparse
from typing import Optional


def run(config: Optional[dict] = None) -> None:
    """Convert NDJSON stream to XML.

    Config keys:
        root_element: Root element name (default: 'root')
        item_element: Element name for each record (default: 'item')
        pretty: Pretty-print output (default: True)
        encoding: Output encoding (default: 'utf-8')

    Reads NDJSON from stdin, writes XML to stdout.
    """
    import xmltodict

    config = config or {}
    root_element = config.get('root_element', 'root')
    item_element = config.get('item_element', 'item')
    pretty = config.get('pretty', True)
    encoding = config.get('encoding', 'utf-8')

    # Read all records
    records = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))

    if not records:
        return

    # Build XML structure
    if len(records) == 1:
        # Single record - use it as root if it's a dict
        if isinstance(records[0], dict):
            xml_dict = {root_element: records[0]}
        else:
            xml_dict = {root_element: {item_element: records[0]}}
    else:
        # Multiple records - wrap in list
        xml_dict = {root_element: {item_element: records}}

    # Convert to XML
    xml_output = xmltodict.unparse(
        xml_dict,
        pretty=pretty,
        indent='  ' if pretty else None,
        encoding=encoding
    )

    print(xml_output)


def schema() -> dict:
    """Return JSON schema for XML writer input.

    XML writer accepts NDJSON with any object structure.
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "description": "NDJSON objects to convert to XML"
    }


def examples() -> list[dict]:
    """Return test cases for this plugin.

    Each example includes:
        - description: What this example demonstrates
        - input: Sample NDJSON input
        - expected_pattern: Pattern to check in output
        - ignore_fields: Fields to ignore when testing (for dynamic values)
    """
    return [
        {
            "description": "Single record to XML",
            "input": '{"name": "Alice", "age": 30}\n',
            "expected_pattern": "<root>\n  <name>Alice</name>\n  <age>30</age>\n</root>",
            "ignore_fields": set()  # Output is deterministic
        },
        {
            "description": "Multiple records to XML list",
            "input": '{"name": "Alice"}\n{"name": "Bob"}\n',
            "config": {"item_element": "person"},
            "expected_pattern": "<person>",
            "ignore_fields": set()
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
    parser = argparse.ArgumentParser(description='Write NDJSON to XML format')
    parser.add_argument('--root-element', default='root',
                        help='Root element name (default: root)')
    parser.add_argument('--item-element', default='item',
                        help='Item element name (default: item)')
    parser.add_argument('--compact', action='store_true',
                        help='Compact output (no pretty printing)')
    parser.add_argument('--examples', action='store_true', help='Show usage examples')
    parser.add_argument('--test', action='store_true', help='Run built-in tests')
    parser.add_argument('--schema', action='store_true', help='Output JSON schema')

    args = parser.parse_args()

    if args.schema:
        print(json.dumps(schema(), indent=2))
        sys.exit(0)

    if args.examples:
        print(json.dumps(examples(), indent=2))
    elif args.test:
        success = test()
        sys.exit(0 if success else 1)
    else:
        # Run normal operation
        config = {
            'root_element': args.root_element,
            'item_element': args.item_element,
            'pretty': not args.compact
        }
        run(config)
