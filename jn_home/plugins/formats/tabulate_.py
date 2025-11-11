#!/usr/bin/env -S uv run --script
"""Format NDJSON as pretty tables for human viewing."""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "tabulate>=0.9.0",
# ]
# [tool.jn]
# matches = [
#   "^-$",
#   ".*\\.table$",
#   "^stdout$"
# ]
# ///

import json
import sys
from typing import Iterator, Optional

from tabulate import tabulate


def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, write as pretty table to stdout.

    Config:
        tablefmt: Table format (default: 'simple')
            Options: plain, simple, grid, fancy_grid, pipe, orgtbl,
                     jira, presto, pretty, psql, rst, mediawiki, html,
                     latex, latex_raw, latex_booktabs, tsv
        headers: Column headers to use (default: 'keys' - first record's keys)
        maxcolwidths: Max width per column (default: None)
        showindex: Show row index (default: False)

    Reads all records to display as table.
    """
    config = config or {}
    tablefmt = config.get("tablefmt", "simple")
    headers = config.get("headers", "keys")
    maxcolwidths = config.get("maxcolwidths")
    showindex = config.get("showindex", False)

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
        print("(No data)", file=sys.stderr)
        return

    # Convert to table
    table = tabulate(
        records,
        headers=headers,
        tablefmt=tablefmt,
        maxcolwidths=maxcolwidths,
        showindex=showindex
    )

    print(table)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Tabulate format plugin - pretty-print tables for humans"
    )
    parser.add_argument(
        "--mode",
        choices=["write"],
        help="Operation mode (tabulate only supports write mode)",
    )
    parser.add_argument(
        "--tablefmt",
        default="simple",
        choices=[
            "plain", "simple", "grid", "fancy_grid", "pipe", "orgtbl",
            "jira", "presto", "pretty", "psql", "rst", "mediawiki",
            "html", "latex", "latex_raw", "latex_booktabs", "tsv"
        ],
        help="Table format style (default: simple)"
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

    args = parser.parse_args()

    if not args.mode:
        parser.error("--mode is required")

    if args.mode != "write":
        parser.error("Tabulate plugin only supports write mode")

    # Build config
    config = {
        "tablefmt": args.tablefmt,
        "showindex": args.showindex,
    }

    if args.maxcolwidths:
        config["maxcolwidths"] = args.maxcolwidths

    writes(config)
