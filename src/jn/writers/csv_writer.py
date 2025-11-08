"""CSV writer for NDJSON data."""

import csv
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, TextIO


def write_csv(
    records: Iterator[Dict[str, Any]],
    output_file: str | Path | None = None,
    delimiter: str = ",",
    header: bool = True,
    append: bool = False,
) -> None:
    """Write NDJSON records to CSV format.

    Args:
        records: Iterator of JSON objects (dicts)
        output_file: Output file path, or None for stdout
        delimiter: Field delimiter (default: ",")
        header: Whether to include header row (default: True)
        append: Whether to append to existing file (default: False)

    Notes:
        - Column order determined by first record's keys
        - Missing keys in later records result in empty values
        - Handles special characters via CSV quoting rules
    """

    # Collect all records (need to know all keys)
    records_list = list(records)
    if not records_list:
        # Empty input - create empty file or just header
        if output_file:
            mode = "a" if append else "w"
            with open(output_file, mode, newline="") as f:
                if header and not append:
                    writer = csv.writer(f, delimiter=delimiter)
                    writer.writerow([])
        return

    # Get all unique keys (union of all record keys, preserving order)
    all_keys: List[str] = []
    seen = set()
    for record in records_list:
        for key in record.keys():
            if key not in seen:
                all_keys.append(key)
                seen.add(key)

    # Write CSV
    output: TextIO
    if output_file:
        mode = "a" if append else "w"
        output = open(output_file, mode, newline="")
    else:
        output = sys.stdout

    try:
        writer = csv.DictWriter(output, fieldnames=all_keys, delimiter=delimiter)
        if header and not append:
            writer.writeheader()
        writer.writerows(records_list)
    finally:
        if output_file:
            output.close()
