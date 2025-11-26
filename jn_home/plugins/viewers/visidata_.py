#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# type = "viewer"
# description = "Interactive data exploration with VisiData"
# ///
"""
VisiData viewer plugin for jn.

Launches VisiData as a separate process to view NDJSON data interactively.
VisiData is a powerful terminal spreadsheet for exploring and arranging
tabular data.

Usage:
    # Via jn commands
    jn cat data.csv | jn view
    jn cat data.csv | jn vd

    # Direct invocation
    jn cat data.csv | uv run --script visidata_.py
    jn cat data.csv | ./visidata_.py

    # With arguments
    ./visidata_.py --filetype jsonl < data.jsonl
    ./visidata_.py --filetype csv < data.csv

VisiData Quick Reference:
    q       Quit
    j/k     Move down/up
    h/l     Move left/right
    /       Search column
    g/      Search all columns
    [       Sort ascending
    ]       Sort descending
    Shift+F Frequency table for column
    Shift+I Describe column statistics
    .       Select current row
    s       Select current row (same as .)
    u       Unselect current row
    g.      Select all matching rows
    "       Open selected rows as new sheet
    (       Expand nested column
    )       Contract column
    z^Y     Python object viewer for cell
    Ctrl+H  Help

Requires: uv tool install visidata
"""

import os
import shutil
import subprocess
import sys


def find_visidata() -> str | None:
    """Find VisiData executable."""
    return shutil.which("vd") or shutil.which("visidata")


def main() -> int:
    """Launch VisiData with stdin data."""
    import argparse

    parser = argparse.ArgumentParser(
        description="View data interactively with VisiData"
    )
    parser.add_argument(
        "--filetype",
        "-f",
        default="jsonl",
        help="Input file type (default: jsonl)",
    )
    parser.add_argument(
        "file",
        nargs="?",
        default="-",
        help="File to view (default: stdin)",
    )
    args = parser.parse_args()

    # Find VisiData
    vd_path = find_visidata()
    if not vd_path:
        print(
            "Error: VisiData not found. Install with: uv tool install visidata",
            file=sys.stderr,
        )
        return 1

    # Build VisiData command
    vd_cmd = [vd_path, "-f", args.filetype]

    if args.file == "-":
        # Reading from stdin - use "-" to tell vd to read stdin
        vd_cmd.append("-")
        stdin = sys.stdin
    else:
        # Reading from file
        vd_cmd.append(args.file)
        stdin = None

    # Launch VisiData
    try:
        proc = subprocess.run(vd_cmd, stdin=stdin)
        return proc.returncode
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"Error launching VisiData: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
