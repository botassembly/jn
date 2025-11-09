#!/usr/bin/env python3
"""Read YAML files and output NDJSON.

Parses YAML files and converts to JSON Lines format.
Supports both single documents and multi-document streams.
"""
# /// script
# dependencies = ["PyYAML>=6.0"]
# ///
# META: type=source, handles=[".yaml", ".yml"], streaming=true
# KEYWORDS: yaml, yml, data, parsing, configuration
# DESCRIPTION: Read YAML files and output NDJSON

import sys
import json
import argparse
from typing import Iterator, Optional


def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Read YAML from stdin, yield records as dicts.

    Config keys:
        safe: Use safe_load instead of load (default: True)
        multi_document: Handle multi-document YAML streams (default: True)

    Yields:
        Dict per YAML document. If document is a list, yields each element.
    """
    import yaml

    config = config or {}
    safe = config.get('safe', True)
    multi_document = config.get('multi_document', True)

    # Read all input
    content = sys.stdin.read()

    # Parse YAML
    if multi_document:
        # Handle multi-document streams (---separated)
        loader = yaml.safe_load_all if safe else yaml.load_all
        documents = loader(content)
    else:
        # Single document
        loader = yaml.safe_load if safe else yaml.load
        documents = [loader(content)]

    # Yield records
    for doc in documents:
        if doc is None:
            continue
        elif isinstance(doc, list):
            # If document is a list, yield each element
            for item in doc:
                if isinstance(item, dict):
                    yield item
                else:
                    # Wrap non-dict items
                    yield {'value': item}
        elif isinstance(doc, dict):
            yield doc
        else:
            # Wrap scalar values
            yield {'value': doc}


def schema() -> dict:
    """Return JSON schema for YAML output.

    YAML reader can output any valid YAML structure as JSON.
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "description": "YAML document as JSON object"
    }


def examples() -> list[dict]:
    """Return test cases for this plugin.

    Each example includes:
        - description: What this example demonstrates
        - input: Sample input data
        - expected: Expected output records
        - ignore_fields: Fields to ignore when testing (for dynamic values)
    """
    return [
        {
            "description": "Simple YAML object",
            "input": """
name: Alice
age: 30
city: NYC
""",
            "expected": [
                {"name": "Alice", "age": 30, "city": "NYC"}
            ],
            "ignore_fields": set()  # All values deterministic
        },
        {
            "description": "YAML list of objects",
            "input": """
- name: Alice
  age: 30
- name: Bob
  age: 25
""",
            "expected": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ],
            "ignore_fields": set()
        },
        {
            "description": "Multi-document YAML",
            "input": """
name: Alice
age: 30
---
name: Bob
age: 25
""",
            "expected": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ],
            "ignore_fields": set()
        },
        {
            "description": "Nested YAML structure",
            "input": """
user:
  name: Alice
  address:
    city: NYC
    zip: 10001
""",
            "expected": [
                {
                    "user": {
                        "name": "Alice",
                        "address": {"city": "NYC", "zip": 10001}
                    }
                }
            ],
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
    parser = argparse.ArgumentParser(description='Read YAML files and output NDJSON')
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
        for record in run():
            print(json.dumps(record))
