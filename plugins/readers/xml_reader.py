#!/usr/bin/env python3
"""Read XML files and output NDJSON.

Parses XML files and converts to JSON Lines format.
Supports element-based streaming for large XML files.
"""
# /// script
# dependencies = ["xmltodict>=0.13.0"]
# ///
# META: type=source, handles=[".xml"], streaming=true

import sys
import json
import argparse
from typing import Iterator, Optional


def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Read XML from stdin, yield records as dicts.

    Config keys:
        root_element: Element to extract as records (default: None = whole doc)
        list_element: Element name that contains list items (default: 'item')
        flatten: Flatten XML attributes (default: False)

    Yields:
        Dict per XML element.
    """
    import xmltodict

    config = config or {}
    root_element = config.get('root_element')
    list_element = config.get('list_element', 'item')
    flatten = config.get('flatten', False)

    # Read all input
    content = sys.stdin.read()

    # Parse XML
    try:
        parsed = xmltodict.parse(content, attr_prefix='', cdata_key='text' if not flatten else '')
    except Exception as e:
        print(f"Error parsing XML: {e}", file=sys.stderr)
        return

    # Extract records
    if root_element:
        # Navigate to specific element
        data = parsed
        for part in root_element.split('.'):
            if isinstance(data, dict) and part in data:
                data = data[part]
            else:
                return
    else:
        # Use root
        data = parsed

    # Yield records
    if isinstance(data, dict):
        # Check if this dict contains a list element
        if list_element in data:
            items = data[list_element]
            if isinstance(items, list):
                yield from items
            else:
                yield items
        else:
            # Single record
            yield data
    elif isinstance(data, list):
        # List of records
        yield from data
    else:
        # Wrap scalar
        yield {'value': data}


def examples() -> list[dict]:
    """Return test cases for this plugin.

    Each example includes:
        - description: What this example demonstrates
        - input: Sample input data
        - expected: Expected output records
    """
    return [
        {
            "description": "Simple XML object",
            "input": """<?xml version="1.0"?>
<person>
  <name>Alice</name>
  <age>30</age>
</person>
""",
            "expected": [
                {"person": {"name": "Alice", "age": "30"}}
            ]
        },
        {
            "description": "XML list of items",
            "input": """<?xml version="1.0"?>
<people>
  <item>
    <name>Alice</name>
    <age>30</age>
  </item>
  <item>
    <name>Bob</name>
    <age>25</age>
  </item>
</people>
""",
            "config": {"root_element": "people"},
            "expected": [
                {"name": "Alice", "age": "30"},
                {"name": "Bob", "age": "25"}
            ]
        },
        {
            "description": "XML with attributes",
            "input": """<?xml version="1.0"?>
<user id="123" role="admin">
  <name>Alice</name>
</user>
""",
            "expected": [
                {"user": {"id": "123", "role": "admin", "name": "Alice"}}
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
    parser = argparse.ArgumentParser(description='Read XML files and output NDJSON')
    parser.add_argument('--root-element', help='Root element to extract records from')
    parser.add_argument('--list-element', default='item', help='List element name (default: item)')
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
        config = {}
        if args.root_element:
            config['root_element'] = args.root_element
        if args.list_element:
            config['list_element'] = args.list_element

        for record in run(config):
            print(json.dumps(record))
