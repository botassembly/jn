#!/usr/bin/env -S uv run --script
"""Parse and format tables with round-trip support for NDJSON."""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "tabulate>=0.9.0",
# ]
# [tool.jn]
# matches = [
#   ".*\\.table$",
#   ".*\\.tbl$",
#   "^-$",
#   "^stdout$"
# ]
# ///

import json
import re
import sys
from html.parser import HTMLParser
from typing import Iterator, Optional


class TableHTMLParser(HTMLParser):
    """Parse HTML tables into rows of data."""

    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = []
        self.current_row = []
        self.current_cell = []
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.headers = []
        self.in_header = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
            self.current_table = []
            self.headers = []
        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.current_row = []
        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.current_cell = []
            if tag == "th":
                self.in_header = True

    def handle_endtag(self, tag):
        if tag == "table":
            if self.current_table:
                self.tables.append({
                    "headers": self.headers,
                    "rows": self.current_table
                })
            self.in_table = False
        elif tag == "tr" and self.in_row:
            if self.in_header and self.current_row:
                self.headers = self.current_row
                self.in_header = False
            elif self.current_row:
                self.current_table.append(self.current_row)
            self.in_row = False
        elif tag in ("td", "th") and self.in_cell:
            cell_text = "".join(self.current_cell).strip()
            self.current_row.append(cell_text)
            self.in_cell = False
            self.current_cell = []

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell.append(data)


def _parse_value(value: str):
    """Parse a string value to appropriate Python type."""
    value = value.strip()

    # Handle empty/null
    if not value or value.lower() in ("null", "none"):
        return None

    # Handle boolean
    value_lower = value.lower()
    if value_lower == "true":
        return True
    if value_lower == "false":
        return False

    # Handle numbers
    try:
        if "." not in value and "e" not in value.lower():
            return int(value)
        return float(value)
    except ValueError:
        return value


def _strip_edges(values: list[str]) -> list[str]:
    """Remove one leading/trailing empty string from list (from pipes)."""
    if values and values[0] == "":
        values = values[1:]
    if values and values[-1] == "":
        values = values[:-1]
    return values


def _parse_pipe_table(lines: list[str]) -> Iterator[dict]:
    """Parse markdown/pipe-delimited tables.

    Format:
        | col1 | col2 |
        |------|------|
        | val1 | val2 |
    """
    if not lines:
        return

    # Find header line (first line with pipes)
    header_idx = None
    for i, line in enumerate(lines):
        if "|" in line:
            header_idx = i
            break

    if header_idx is None:
        return

    # Parse header
    header_line = lines[header_idx]
    headers = [h.strip() for h in header_line.split("|") if h.strip()]

    if not headers:
        return

    # Skip separator line (usually next line with dashes)
    start_idx = header_idx + 1
    if start_idx < len(lines) and re.match(r"^\s*\|[\s\-:|]+\|\s*$", lines[start_idx]):
        start_idx += 1

    # Parse data rows
    for line in lines[start_idx:]:
        line = line.strip()
        if not line or "|" not in line:
            continue

        # Skip separator lines
        if re.match(r"^\s*\|[\s\-:|]+\|\s*$", line):
            continue

        # Split by pipes, strip, and remove leading/trailing empty strings
        values = _strip_edges([v.strip() for v in line.split("|")])

        # Match values to headers
        if len(values) >= len(headers):
            record = {}
            for header, value in zip(headers, values):
                record[header] = _parse_value(value)
            yield record


def _parse_grid_table(lines: list[str]) -> Iterator[dict]:
    """Parse grid/box-drawing tables.

    Formats:
        +------+------+
        | col1 | col2 |
        +------+------+
        | val1 | val2 |
        +------+------+

    Or fancy_grid with box-drawing chars:
        ╒══════╤══════╕
        │ col1 │ col2 │
        ╞══════╪══════╡
        │ val1 │ val2 │
        ╘══════╧══════╛
    """
    if not lines:
        return

    # Find border characters
    border_chars = {"+", "-", "=", "│", "├", "┤", "╒", "╞", "╘", "╤", "╪", "╧", "═", "╕", "╡", "╛"}

    # Find header line (first line with content that's not all borders)
    header_idx = None
    for i, line in enumerate(lines):
        # Skip pure border lines
        if all(c in border_chars or c.isspace() for c in line):
            continue
        if "|" in line or "│" in line:
            header_idx = i
            break

    if header_idx is None:
        return

    # Parse header
    header_line = lines[header_idx]
    # Split by | or │
    separators = re.split(r"[|│]", header_line)
    headers = [h.strip() for h in separators if h.strip()]

    if not headers:
        return

    # Parse data rows (skip header and border lines)
    for i, line in enumerate(lines[header_idx + 1:], start=header_idx + 1):
        # Skip border lines
        if all(c in border_chars or c.isspace() for c in line):
            continue

        # Skip if no separator
        if "|" not in line and "│" not in line:
            continue

        # Split by | or │, strip, and remove leading/trailing empty strings
        values = _strip_edges([v.strip() for v in re.split(r"[|│]", line)])

        # Match values to headers
        if len(values) >= len(headers):
            record = {}
            for header, value in zip(headers, values):
                record[header] = _parse_value(value)
            yield record


def _parse_html_table(html: str) -> Iterator[dict]:
    """Parse HTML tables."""
    parser = TableHTMLParser()
    parser.feed(html)

    for table in parser.tables:
        headers = table["headers"]
        for row in table["rows"]:
            if len(row) >= len(headers):
                record = {}
                for header, value in zip(headers, row):
                    record[header] = _parse_value(value)
                yield record


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read tables from stdin, yield NDJSON records.

    Config:
        format: Table format to parse (default: 'auto')
            Options: auto, pipe, grid, html

    Supports:
        - Markdown/pipe tables (| col1 | col2 |)
        - Grid tables (+----+----+)
        - Fancy grid tables with box-drawing characters
        - HTML tables (<table>...</table>)

    Yields:
        Dict per table row with column headers as keys
    """
    config = config or {}
    table_format = config.get("format", "auto")

    # Read all input (tables need full context to parse)
    lines = [line.rstrip("\n\r") for line in sys.stdin]
    full_text = "\n".join(lines)

    # Auto-detect format if needed
    if table_format == "auto":
        if "<table" in full_text.lower():
            table_format = "html"
        elif re.search(r"^\s*[|│]", full_text, re.MULTILINE):
            # Has | or │ at start of lines
            if re.search(r"[+╒╞╘╤╪╧═╕╡╛]", full_text):
                table_format = "grid"
            else:
                table_format = "pipe"
        elif re.search(r"^\s*\+[-=]+\+", full_text, re.MULTILINE):
            table_format = "grid"
        else:
            # Default to pipe
            table_format = "pipe"

    # Parse based on format
    if table_format == "html":
        yield from _parse_html_table(full_text)
    elif table_format == "grid":
        yield from _parse_grid_table(lines)
    elif table_format == "pipe":
        yield from _parse_pipe_table(lines)
    else:
        print(f"Warning: Unknown table format '{table_format}'", file=sys.stderr)


def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, write as formatted table to stdout.

    Config:
        tablefmt: Table format (default: 'grid')
            Options: plain, simple, grid, fancy_grid, pipe, orgtbl,
                     github, jira, presto, pretty, psql, rst, mediawiki,
                     html, latex, latex_raw, latex_booktabs, tsv, rounded_grid,
                     heavy_grid, mixed_grid, double_grid, outline, simple_outline,
                     rounded_outline, heavy_outline, mixed_outline, double_outline
        headers: Column headers to use (default: 'keys' - first record's keys)
        maxcolwidths: Max width per column (default: None)
        showindex: Show row index (default: False)
        numalign: Number alignment (default: 'decimal')
        stralign: String alignment (default: 'left')

    Reads all records to display as table.
    """
    config = config or {}
    tablefmt = config.get("tablefmt", "grid")
    headers = config.get("headers", "keys")
    maxcolwidths = config.get("maxcolwidths")
    showindex = config.get("showindex", False)
    numalign = config.get("numalign", "decimal")
    stralign = config.get("stralign", "left")

    # Collect all records
    records = []
    for line in sys.stdin:
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping invalid JSON line: {e}", file=sys.stderr)
                continue

    if not records:
        # Empty input
        return

    # Import here to avoid import cost if not needed
    from tabulate import tabulate

    # Convert to table
    table = tabulate(
        records,
        headers=headers,
        tablefmt=tablefmt,
        maxcolwidths=maxcolwidths,
        showindex=showindex,
        numalign=numalign,
        stralign=stralign,
    )

    print(table)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Table format plugin - read and write tables with round-trip support"
    )
    parser.add_argument(
        "--mode",
        choices=["read", "write"],
        help="Operation mode: read table to NDJSON, or write NDJSON to table",
    )

    # Read options
    parser.add_argument(
        "--format",
        default="auto",
        choices=["auto", "pipe", "grid", "html"],
        help="Table format to parse when reading (default: auto)"
    )

    # Write options
    parser.add_argument(
        "--tablefmt",
        default="grid",
        help="Table format style when writing (default: grid)"
    )
    parser.add_argument(
        "--maxcolwidths",
        type=int,
        help="Maximum column width"
    )
    parser.add_argument(
        "--showindex",
        action="store_true",
        help="Show row index"
    )
    parser.add_argument(
        "--numalign",
        default="decimal",
        choices=["left", "right", "center", "decimal"],
        help="Number alignment (default: decimal)"
    )
    parser.add_argument(
        "--stralign",
        default="left",
        choices=["left", "right", "center"],
        help="String alignment (default: left)"
    )

    args = parser.parse_args()

    if not args.mode:
        parser.error("--mode is required")

    # Build config
    if args.mode == "read":
        config = {
            "format": args.format,
        }
        for record in reads(config):
            print(json.dumps(record), flush=True)
    else:
        config = {
            "tablefmt": args.tablefmt,
            "showindex": args.showindex,
            "numalign": args.numalign,
            "stralign": args.stralign,
        }

        if args.maxcolwidths:
            config["maxcolwidths"] = args.maxcolwidths

        writes(config)
