#!/usr/bin/env python3
"""Read CSV files and output NDJSON - IMPROVED VERSION WITH SCHEMA

This is an example of the improved testing pattern with:
- JSON schema for output validation
- Reusable test framework
- Smart field matching (exact vs semantic)
- Better agent introspection
"""
# /// script
# dependencies = []
# ///
# META: type=source, handles=[".csv", ".tsv"], streaming=true

import csv
import json
import sys
from typing import Iterator, Optional


def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Read CSV from stdin, yield records as dicts.

    Config keys:
        delimiter: Field delimiter (default: ',')
        skip_rows: Number of rows to skip (default: 0)

    Yields:
        Dict per CSV row with column headers as keys
    """
    config = config or {}
    delimiter = config.get('delimiter', ',')
    skip_rows = config.get('skip_rows', 0)

    # Skip header rows if requested
    for _ in range(skip_rows):
        next(sys.stdin)

    # Read CSV
    reader = csv.DictReader(sys.stdin, delimiter=delimiter)

    for row in reader:
        yield row


def schema() -> dict:
    """Return JSON schema for CSV output.

    This allows:
    - Automatic validation of output
    - Agent introspection of capabilities
    - Type checking without hardcoded tests
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "description": "CSV row as key-value pairs",
        "patternProperties": {
            ".*": {
                "type": "string",
                "description": "All CSV values are strings"
            }
        }
    }


def examples() -> list[dict]:
    """Return test cases with smart field checking.

    New format includes:
    - checks.exact: Fields that must match exactly
    - checks.types: Fields that must match type only
    - checks.patterns: Fields that must match regex
    - checks.ranges: Numeric fields with min/max
    """
    return [
        {
            "description": "Basic CSV with header",
            "input": "name,age\nAlice,30\nBob,25\n",
            "expected": [
                {"name": "Alice", "age": "30"},
                {"name": "Bob", "age": "25"}
            ],
            "checks": {
                # These fields must match exactly
                "exact": ["name", "age"],
                # All fields must be strings (CSV reader outputs strings)
                "types": ["name", "age"]
            }
        },
        {
            "description": "TSV (tab-separated)",
            "config": {"delimiter": "\t"},
            "input": "name\tage\nAlice\t30\nBob\t25\n",
            "expected": [
                {"name": "Alice", "age": "30"},
                {"name": "Bob", "age": "25"}
            ],
            "checks": {
                "exact": ["name", "age"]
            }
        },
        {
            "description": "CSV with special characters",
            "input": 'name,email\nAlice,alice@example.com\n',
            "expected": [
                {"name": "Alice", "email": "alice@example.com"}
            ],
            "checks": {
                "exact": ["name"],
                # Email must match pattern
                "patterns": {
                    "email": r"^[^@]+@[^@]+\.[^@]+$"
                }
            }
        }
    ]


def test() -> bool:
    """Run built-in tests using reusable framework.

    Much cleaner - no boilerplate!
    """
    # Import from jn testing framework
    import sys
    from pathlib import Path

    # Add src to path so we can import jn.testing
    jn_path = Path(__file__).parent.parent.parent / 'src'
    if str(jn_path) not in sys.path:
        sys.path.insert(0, str(jn_path))

    try:
        from jn.testing import run_plugin_tests

        # All the test logic is handled by the framework!
        return run_plugin_tests(
            run_func=run,
            examples_func=examples,
            schema_func=schema,
            verbose=True
        )
    except ImportError:
        # Fallback if framework not available
        print("Warning: jn.testing not available, using basic tests", file=sys.stderr)
        return test_basic()


def test_basic() -> bool:
    """Fallback basic test without framework."""
    from io import StringIO

    passed = 0
    failed = 0

    for example in examples():
        desc = example['description']
        try:
            sys.stdin = StringIO(example['input'])
            config = example.get('config', {})
            results = list(run(config))
            expected = example['expected']

            if results == expected:
                print(f"✓ {desc}", file=sys.stderr)
                passed += 1
            else:
                print(f"✗ {desc}", file=sys.stderr)
                failed += 1

        except Exception as e:
            print(f"✗ {desc}: {e}", file=sys.stderr)
            failed += 1

    print(f"\n{passed} passed, {failed} failed", file=sys.stderr)
    return failed == 0


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Read CSV/TSV and output NDJSON'
    )
    parser.add_argument(
        '--delimiter',
        default=',',
        help='Field delimiter (default: comma)'
    )
    parser.add_argument(
        '--skip-rows',
        type=int,
        default=0,
        help='Number of rows to skip'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run built-in tests'
    )
    parser.add_argument(
        '--schema',
        action='store_true',
        help='Output JSON schema for this plugin'
    )

    args = parser.parse_args()

    if args.schema:
        # Agent introspection: output schema
        print(json.dumps(schema(), indent=2))
    elif args.test:
        success = test()
        sys.exit(0 if success else 1)
    else:
        # Normal operation
        config = {
            'delimiter': args.delimiter,
            'skip_rows': args.skip_rows
        }

        for record in run(config):
            print(json.dumps(record), flush=True)
