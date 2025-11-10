#!/usr/bin/env python3
"""Read CSV files and output NDJSON.

Harvested from oldgen jcparsers logic with adaptations.
"""
# /// script
# dependencies = []
# ///
# META: type=source, handles=[".csv", ".tsv"], streaming=true
# KEYWORDS: csv, tsv, data, parsing, tabular
# DESCRIPTION: Read CSV/TSV files and output NDJSON

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

    CSV reader outputs records as objects with string values.
    Field names come from the header row.
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
    """Return test cases for this plugin.

    Each example includes:
        - description: What this example demonstrates
        - input: Sample input data
        - expected: Expected output records
        - ignore_fields: Fields to ignore when testing (for dynamic values)
    """
    return [
        {
            "description": "Basic CSV with header",
            "input": "name,age\nAlice,30\nBob,25\n",
            "expected": [
                {"name": "Alice", "age": "30"},
                {"name": "Bob", "age": "25"}
            ],
            "ignore_fields": set()  # All values are deterministic
        },
        {
            "description": "TSV (tab-separated)",
            "config": {"delimiter": "\t"},
            "input": "name\tage\nAlice\t30\nBob\t25\n",
            "expected": [
                {"name": "Alice", "age": "30"},
                {"name": "Bob", "age": "25"}
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

    for example in examples():
        desc = example['description']
        try:
            # Setup stdin with test input
            sys.stdin = StringIO(example['input'])

            # Run with config if provided
            config = example.get('config', {})
            results = list(run(config))

            # Validate output
            expected = example['expected']
            if results == expected:
                print(f"✓ {desc}", file=sys.stderr)
                passed += 1
            else:
                print(f"✗ {desc}: Output mismatch", file=sys.stderr)
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
        help='Output JSON schema'
    )

    args = parser.parse_args()

    if args.schema:
        print(json.dumps(schema(), indent=2))
        sys.exit(0)

    if args.test:
        success = test()
        sys.exit(0 if success else 1)
    else:
        # Normal operation: read from stdin, write NDJSON to stdout
        config = {
            'delimiter': args.delimiter,
            'skip_rows': args.skip_rows
        }

        for record in run(config):
            print(json.dumps(record), flush=True)
