#!/usr/bin/env -S uv run --script
"""Parse XLSX (Excel) files and convert to NDJSON."""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "openpyxl>=3.1.0"
# ]
# [tool.jn]
# matches = [
#   ".*\\.xlsx$",
#   ".*\\.xlsm$"
# ]
# ///

import io
import json
import sys
from typing import Iterator, Optional


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read XLSX from stdin, yield NDJSON records.

    Config:
        sheet: Sheet name or index (default: 0 for first sheet)
        skip_rows: Number of rows to skip before header (default: 0)

    Yields:
        Dict per Excel row with column headers as keys
    """
    import openpyxl

    config = config or {}
    sheet_selector = config.get("sheet", 0)
    skip_rows = config.get("skip_rows", 0)

    # Read binary data from stdin
    xlsx_data = sys.stdin.buffer.read()

    # Load workbook from memory
    workbook = openpyxl.load_workbook(io.BytesIO(xlsx_data), read_only=True, data_only=True)

    # Select sheet
    if isinstance(sheet_selector, int):
        # Select by index
        sheet_names = workbook.sheetnames
        if sheet_selector < 0 or sheet_selector >= len(sheet_names):
            raise ValueError(f"Sheet index {sheet_selector} out of range (0-{len(sheet_names)-1})")
        sheet = workbook[sheet_names[sheet_selector]]
    else:
        # Select by name
        if sheet_selector not in workbook.sheetnames:
            raise ValueError(f"Sheet '{sheet_selector}' not found. Available: {workbook.sheetnames}")
        sheet = workbook[sheet_selector]

    # Get rows iterator
    rows = iter(sheet.iter_rows(values_only=True))

    # Skip initial rows if requested
    for _ in range(skip_rows):
        next(rows, None)

    # Read header row
    header = next(rows, None)
    if not header:
        return  # Empty sheet

    # Convert header to strings and filter None values
    header = [str(col) if col is not None else f"Column_{i+1}" for i, col in enumerate(header)]

    # Yield data rows as dictionaries
    for row in rows:
        # Skip completely empty rows
        if all(cell is None for cell in row):
            continue

        # Create record dict, padding with None if row is shorter than header
        record = {}
        for i, col_name in enumerate(header):
            value = row[i] if i < len(row) else None
            # Convert datetime objects to ISO format
            if value is not None and hasattr(value, 'isoformat'):
                value = value.isoformat()
            record[col_name] = value

        yield record

    workbook.close()


def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, write XLSX to stdout.

    Config:
        sheet: Sheet name (default: 'Sheet1')

    Reads all records to create workbook, then writes binary XLSX.
    """
    import openpyxl

    config = config or {}
    sheet_name = config.get("sheet", "Sheet1")

    # Collect all records (need to know all keys for header)
    records = []
    for line in sys.stdin:
        line = line.strip()
        if line:
            records.append(json.loads(line))

    # Create workbook
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = sheet_name

    if not records:
        # Empty input - create empty workbook
        output = io.BytesIO()
        workbook.save(output)
        sys.stdout.buffer.write(output.getvalue())
        return

    # Get all unique keys (union, preserving order of first appearance)
    all_keys = []
    seen = set()
    for record in records:
        for key in record:
            if key not in seen:
                all_keys.append(key)
                seen.add(key)

    # Write header row
    for col_idx, key in enumerate(all_keys, start=1):
        sheet.cell(row=1, column=col_idx, value=key)

    # Write data rows
    for row_idx, record in enumerate(records, start=2):
        for col_idx, key in enumerate(all_keys, start=1):
            value = record.get(key)
            sheet.cell(row=row_idx, column=col_idx, value=value)

    # Write to stdout
    output = io.BytesIO()
    workbook.save(output)
    sys.stdout.buffer.write(output.getvalue())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="XLSX format plugin - read/write Excel files"
    )
    parser.add_argument(
        "--mode",
        choices=["read", "write"],
        help="Operation mode: read XLSX to NDJSON, or write NDJSON to XLSX",
    )
    parser.add_argument(
        "--sheet",
        help="Sheet name or index (default: 0 for first sheet when reading, 'Sheet1' when writing)",
    )
    parser.add_argument(
        "--skip-rows",
        type=int,
        default=0,
        help="Number of rows to skip before header when reading",
    )

    args = parser.parse_args()

    if not args.mode:
        parser.error("--mode is required")

    # Build config
    config = {}

    if args.sheet:
        # Try to convert to int if it looks like a number
        try:
            config["sheet"] = int(args.sheet)
        except ValueError:
            config["sheet"] = args.sheet

    if args.mode == "read":
        if args.skip_rows:
            config["skip_rows"] = args.skip_rows
        for record in reads(config):
            print(json.dumps(record), flush=True)
    else:
        writes(config)
