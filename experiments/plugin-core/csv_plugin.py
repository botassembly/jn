#!/usr/bin/env python3
"""CSV Plugin using jn_plugin core library.

This demonstrates how the core library reduces a 278-line plugin to ~70 lines.

Compare with: jn_home/plugins/formats/csv_.py (278 lines)
"""

import csv
import sys
from jn_plugin import Plugin, read_ndjson_all, write_ndjson

# Create plugin with metadata
plugin = Plugin("csv", "Parse CSV/TSV files and convert to/from NDJSON")
plugin.matches(r".*\.csv$", r".*\.tsv$", r".*\.txt$")

# Add format-specific arguments
plugin.arg("--delimiter", default="auto", help="Field delimiter (default: auto-detect)")
plugin.arg("--skip-rows", type=int, default=0, help="Number of rows to skip")
plugin.arg("--no-header", dest="header", action="store_false", help="Skip header when writing")


def _detect_delimiter(sample_lines: list[str], candidates: str = ",;\t|") -> tuple[str, bool]:
    """Auto-detect delimiter using heuristic scoring."""
    if not sample_lines:
        return ",", False

    best_delim = ","
    best_score = float("-inf")
    found = False

    for delim in candidates:
        col_counts = []
        for line in sample_lines:
            if delim not in line:
                continue
            cols = line.split(delim)
            if len(cols) > 1:
                col_counts.append(len(cols))

        if len(col_counts) < 3:
            continue

        found = True
        n = len(col_counts)
        mean_cols = sum(col_counts) / n
        variance = sum((c - mean_cols) ** 2 for c in col_counts) / n
        score = n - 5 * variance

        if score > best_score:
            best_score = score
            best_delim = delim

    return best_delim, found


@plugin.reader
def reads(config: dict):
    """Read CSV from stdin, yield NDJSON records."""
    from itertools import chain

    delimiter = config.get("delimiter", "auto")
    skip_rows = config.get("skip_rows", 0)

    # Sample lines for delimiter detection
    sample_lines = []
    for i, line in enumerate(sys.stdin):
        sample_lines.append(line)
        if i >= 50:
            break

    # Auto-detect delimiter
    if delimiter == "auto":
        detected, found = _detect_delimiter(sample_lines)
        delimiter = detected if found else ","

    # Chain sample with remaining stdin
    stdin_content = chain(sample_lines, sys.stdin)

    class LineReader:
        def __init__(self, it):
            self.it = it
        def __iter__(self):
            return self.it

    reader = LineReader(stdin_content)

    # Skip rows
    for _ in range(skip_rows):
        next(reader.it, None)

    # Read CSV
    csv_reader = csv.DictReader(reader, delimiter=delimiter)
    yield from csv_reader


@plugin.writer
def writes(config: dict):
    """Read NDJSON from stdin, write CSV to stdout."""
    delimiter = config.get("delimiter", ",")
    if delimiter == "auto":
        delimiter = ","
    include_header = config.get("header", True)

    records = read_ndjson_all()
    if not records:
        return

    # Get all unique keys (preserving order)
    all_keys = []
    seen = set()
    for record in records:
        for key in record:
            if key not in seen:
                all_keys.append(key)
                seen.add(key)

    # Write CSV
    writer = csv.DictWriter(sys.stdout, fieldnames=all_keys, delimiter=delimiter)
    if include_header:
        writer.writeheader()
    writer.writerows(records)


if __name__ == "__main__":
    plugin.run()
