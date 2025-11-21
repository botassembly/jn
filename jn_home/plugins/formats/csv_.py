#!/usr/bin/env -S uv run --script
"""Parse CSV/TSV files and convert to/from NDJSON."""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = [
#   ".*\\.csv$",
#   ".*\\.tsv$",
#   ".*\\.txt$"
# ]
# ///

import csv
import json
import sys
from typing import Iterator, Optional


def _detect_delimiter(
    sample_lines: list[str], candidates: str = ",;\t|"
) -> tuple[str, bool]:
    """Auto-detect delimiter using heuristic scoring.

    Args:
        sample_lines: First N lines of the file (typically 20-100)
        candidates: String of candidate delimiters to try

    Returns:
        Tuple of (best_delimiter, has_evidence). If has_evidence is False,
        no candidate had enough signal and the caller should fall back to
        a safe default.

    Algorithm:
    - For each candidate delimiter:
      - Count how consistently it appears across lines
      - Penalize high variance in column counts
      - Penalize many empty fields
    - Pick delimiter with highest score
    """
    if not sample_lines:
        return ",", False

    best_delim = ","
    best_score = float("-inf")
    found = False

    for delim in candidates:
        col_counts = []
        empty_fields = 0
        total_fields = 0

        for line in sample_lines:
            # Simple split (not quote-aware for speed, csv.Sniffer handles that)
            if delim not in line:
                continue

            cols = line.split(delim)
            if len(cols) <= 1:
                continue

            col_counts.append(len(cols))
            empty_fields += sum(1 for c in cols if not c.strip())
            total_fields += len(cols)

        # Need at least 3 lines with this delimiter
        if len(col_counts) < 3:
            continue

        found = True

        # Calculate metrics
        n = len(col_counts)
        mean_cols = sum(col_counts) / n
        variance = sum((c - mean_cols) ** 2 for c in col_counts) / n
        empty_ratio = empty_fields / total_fields if total_fields else 0

        # Score: reward consistency, penalize variance and empties
        score = n - 5 * variance - 2 * empty_ratio * n

        if score > best_score:
            best_score = score
            best_delim = delim

    return best_delim, found


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read CSV from stdin, yield NDJSON records.

    Config:
        delimiter: Field delimiter (default: ',', or 'auto' to detect)
        skip_rows: Number of header rows to skip (default: 0)
        limit: Maximum records to yield (default: None)

    Yields:
        Dict per CSV row with column headers as keys
    """
    config = config or {}
    delimiter = config.get("delimiter", "auto")
    skip_rows = config.get("skip_rows", 0)
    limit = config.get("limit")

    # Always read a small sample so we can auto-detect delimiters and
    # sanity-check explicit delimiters.
    from itertools import chain

    sample_lines: list[str] = []
    line_count = 0
    for line in sys.stdin:
        sample_lines.append(line)
        line_count += 1
        if line_count >= 50:
            break

    detected_delim, has_evidence = _detect_delimiter(sample_lines)

    if delimiter == "auto":
        # Auto-detect delimiter from sample when possible; fall back to comma
        # when detection is inconclusive.
        delimiter = detected_delim if has_evidence else ","
    else:
        # Explicit delimiter was configured. If we have strong evidence that
        # the data uses a different delimiter, fail early instead of emitting
        # a misleading one-column schema.
        if has_evidence and detected_delim != delimiter:
            msg = (
                f"Configured delimiter '{delimiter}' does not match detected "
                f"delimiter '{detected_delim}'. Use delimiter=auto or the "
                f"correct delimiter for this file."
            )
            raise SystemExit(msg)

    stdin_content = chain(sample_lines, sys.stdin)

    class ChainedReader:
        def __init__(self, iterator):
            self.iterator = iterator

        def __iter__(self):
            return self.iterator

        def __next__(self):
            return next(self.iterator)

    input_stream = ChainedReader(stdin_content)

    # Skip header rows if requested
    for _ in range(skip_rows):
        next(input_stream, None)

    # Read CSV
    reader = csv.DictReader(input_stream, delimiter=delimiter)

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
    if delimiter == "auto":
        delimiter = ","
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
        "--delimiter",
        default="auto",
        help="Field delimiter (default: auto-detect)",
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
