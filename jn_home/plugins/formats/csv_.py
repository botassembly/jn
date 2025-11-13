#!/usr/bin/env -S uv run --script
"""Parse CSV/TSV files and convert to/from NDJSON."""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = [
#   ".*\\.csv$",
#   ".*\\.tsv$"
# ]
# ///

import csv
import json
import sys
from typing import Iterator, Optional


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read CSV from stdin, yield NDJSON records.

    Config:
        delimiter: Field delimiter (default: ',')
        skip_rows: Number of header rows to skip (default: 0)
        limit: Maximum records to yield (default: None)

    Yields:
        Dict per CSV row with column headers as keys
    """
    config = config or {}
    delimiter = config.get("delimiter", ",")
    skip_rows = config.get("skip_rows", 0)
    limit = config.get("limit")

    # Skip header rows if requested
    for _ in range(skip_rows):
        next(sys.stdin, None)

    # Read CSV
    reader = csv.DictReader(sys.stdin, delimiter=delimiter)

    if limit:
        count = 0
        for row in reader:
            yield row
            count += 1
            if count >= limit:
                break
    else:
        yield from reader


def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, write CSV to stdout.

    Config:
        delimiter: Field delimiter (default: ',')
        header: Include header row (default: True)

    Reads all records to determine column union, then writes CSV.
    """
    config = config or {}
    delimiter = config.get("delimiter", ",")
    include_header = config.get("header", True)

    # Collect all records (need to know all keys for CSV header)
    records = []
    for line in sys.stdin:
        line = line.strip()
        if line:
            records.append(json.loads(line))

    if not records:
        # Empty input
        if include_header:
            writer = csv.writer(sys.stdout, delimiter=delimiter)
            writer.writerow([])
        return

    # Get all unique keys (union, preserving order of first appearance)
    all_keys = []
    seen = set()
    for record in records:
        for key in record:
            if key not in seen:
                all_keys.append(key)
                seen.add(key)

    # Write CSV
    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=all_keys,
        delimiter=delimiter,
        lineterminator="\n",
    )

    if include_header:
        writer.writeheader()

    writer.writerows(records)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="CSV format plugin - read/write CSV files"
    )
    parser.add_argument(
        "--mode",
        choices=["read", "write"],
        help="Operation mode: read CSV to NDJSON, or write NDJSON to CSV",
    )
    parser.add_argument(
        "--delimiter", default=",", help="Field delimiter (default: comma)"
    )
    parser.add_argument(
        "--skip-rows",
        type=int,
        default=0,
        help="Number of rows to skip when reading",
    )
    parser.add_argument(
        "--no-header",
        dest="header",
        action="store_false",
        help="Skip header row when writing",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum records to yield when reading",
    )

    args = parser.parse_args()

    if not args.mode:
        parser.error("--mode is required when not running tests")

    # Build config
    config = {
        "delimiter": args.delimiter,
    }

    if args.mode == "read":
        config["skip_rows"] = args.skip_rows
        if args.limit:
            config["limit"] = args.limit
        for record in reads(config):
            print(json.dumps(record), flush=True)
    else:
        config["header"] = args.header
        writes(config)
