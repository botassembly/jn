#!/usr/bin/env python3
"""Read TOML files and output NDJSON.

Parses TOML configuration files and converts to JSON Lines format.
"""
# /// script
# dependencies = []
# ///
# META: type=source, handles=[".toml"], streaming=false

import sys
import json
import argparse
from typing import Iterator, Optional


def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Read TOML from stdin, yield records as dicts.

    Config keys:
        table: Extract specific table as records (default: None = whole doc)
        array_table: Table containing array of records (default: None)

    Yields:
        Dict per TOML document or table entry.
    """
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # Fallback for older Python
        except ImportError:
            print("Error: tomllib/tomli not available", file=sys.stderr)
            return

    config = config or {}
    table = config.get('table')
    array_table = config.get('array_table')

    # Read all input
    content = sys.stdin.read()

    # Parse TOML
    try:
        parsed = tomllib.loads(content)
    except Exception as e:
        print(f"Error parsing TOML: {e}", file=sys.stderr)
        return

    # Extract records
    if array_table:
        # Extract specific array of tables
        if array_table in parsed and isinstance(parsed[array_table], list):
            yield from parsed[array_table]
        else:
            yield parsed.get(array_table, {})
    elif table:
        # Extract specific table
        if table in parsed:
            data = parsed[table]
            if isinstance(data, dict):
                yield data
            elif isinstance(data, list):
                yield from data
            else:
                yield {'value': data}
        else:
            return
    else:
        # Yield whole document
        yield parsed


def examples() -> list[dict]:
    """Return test cases for this plugin.

    Each example includes:
        - description: What this example demonstrates
        - input: Sample input data
        - expected: Expected output records
    """
    return [
        {
            "description": "Simple TOML document",
            "input": """
title = "Example"
version = "1.0"

[database]
server = "localhost"
port = 5432
""",
            "expected": [
                {
                    "title": "Example",
                    "version": "1.0",
                    "database": {
                        "server": "localhost",
                        "port": 5432
                    }
                }
            ]
        },
        {
            "description": "TOML with array of tables",
            "input": """
[[users]]
name = "Alice"
age = 30

[[users]]
name = "Bob"
age = 25
""",
            "config": {"array_table": "users"},
            "expected": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ]
        },
        {
            "description": "Extract specific table",
            "input": """
[server]
host = "localhost"
port = 8080

[database]
host = "db.local"
port = 5432
""",
            "config": {"table": "server"},
            "expected": [
                {"host": "localhost", "port": 8080}
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
    parser = argparse.ArgumentParser(description='Read TOML files and output NDJSON')
    parser.add_argument('--table', help='Extract specific table')
    parser.add_argument('--array-table', help='Extract array of tables')
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
        if args.table:
            config['table'] = args.table
        if args.array_table:
            config['array_table'] = args.array_table

        for record in run(config):
            print(json.dumps(record))
