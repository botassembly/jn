#!/usr/bin/env python3
"""Write NDJSON to CSV format.

Harvested from oldgen writers/csv_writer.py with adaptations.
"""
# /// script
# dependencies = []
# ///
# META: type=target, handles=[".csv", ".tsv"]
# KEYWORDS: csv, tsv, writer, output, tabular
# DESCRIPTION: Write NDJSON to CSV/TSV format

import csv
import json
import sys
from typing import Iterator, Optional


def run(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, write CSV to stdout.

    Config keys:
        delimiter: Field delimiter (default: ',')
        header: Include header row (default: True)

    Notes:
        - Column order determined by first record's keys
        - Missing keys in later records result in empty values
        - Handles special characters via CSV quoting rules
    """
    config = config or {}
    delimiter = config.get('delimiter', ',')
    header = config.get('header', True)

    # Collect all records (need to know all keys for CSV)
    records = []
    for line in sys.stdin:
        if line.strip():
            records.append(json.loads(line))

    if not records:
        # Empty input - just write header if requested
        if header:
            writer = csv.writer(sys.stdout, delimiter=delimiter)
            writer.writerow([])
        return

    # Get all unique keys (union, preserving order)
    all_keys = []
    seen = set()
    for record in records:
        for key in record:
            if key not in seen:
                all_keys.append(key)
                seen.add(key)

    # Write CSV (lineterminator='\n' ensures Unix line endings)
    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=all_keys,
        delimiter=delimiter,
        lineterminator='\n'
    )

    if header:
        writer.writeheader()

    writer.writerows(records)


def schema() -> dict:
    """Return JSON schema for CSV writer input.

    CSV writer accepts NDJSON with any object structure.
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "description": "NDJSON objects to convert to CSV rows"
    }


def examples() -> list[dict]:
    """Return test cases."""
    return [
        {
            "description": "Basic NDJSON to CSV",
            "input": '{"name": "Alice", "age": 30}\n{"name": "Bob", "age": 25}\n',
            "expected": "name,age\nAlice,30\nBob,25\n",
            "ignore_fields": set()  # Output is deterministic
        },
        {
            "description": "Inconsistent keys (union)",
            "input": '{"name": "Alice", "age": 30}\n{"name": "Bob", "city": "NYC"}\n',
            "expected": "name,age,city\nAlice,30,\nBob,,NYC\n",
            "ignore_fields": set()
        },
        {
            "description": "TSV output",
            "config": {"delimiter": "\t"},
            "input": '{"name": "Alice", "age": 30}\n',
            "expected": "name\tage\nAlice\t30\n",
            "ignore_fields": set()
        }
    ]


def test() -> bool:
    """Run built-in tests."""
    from io import StringIO

    passed = 0
    failed = 0

    for example in examples():
        desc = example['description']
        try:
            # Setup stdin
            sys.stdin = StringIO(example['input'])

            # Capture stdout
            old_stdout = sys.stdout
            sys.stdout = StringIO()

            # Run with config
            config = example.get('config', {})
            run(config)

            # Get output
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

            # Validate
            expected = example['expected']
            if output == expected:
                print(f"✓ {desc}", file=sys.stderr)
                passed += 1
            else:
                print(f"✗ {desc}: Output mismatch", file=sys.stderr)
                print(f"  Expected: {repr(expected)}", file=sys.stderr)
                print(f"  Got: {repr(output)}", file=sys.stderr)
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
        description='Write NDJSON to CSV format'
    )
    parser.add_argument(
        '--delimiter',
        default=',',
        help='Field delimiter (default: comma)'
    )
    parser.add_argument(
        '--no-header',
        dest='header',
        action='store_false',
        help='Skip header row'
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
        config = {
            'delimiter': args.delimiter,
            'header': args.header
        }

        run(config)
