#!/usr/bin/env -S uv run --script
"""Gzip decompression plugin for transparent .gz file handling.

This plugin enables reading .gz compressed files transparently:
- Reads compressed bytes from stdin
- Writes decompressed bytes to stdout
- Operates in raw mode (bytes, not NDJSON)

Examples:
    # Decompress .gz file
    cat file.csv.gz | uv run --script gz_.py --mode raw | csv_.py --mode read

    # JN automatically inserts this in pipeline:
    jn cat file.csv.gz  # → gz (raw) → csv (read)
    jn cat https://example.com/data.json.gz  # → http (raw) → gz (raw) → json (read)
"""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = [
#   ".*\\.gz$"
# ]
# supports_raw = true
# ///

import gzip
import sys


def decompress_stream():
    """Decompress gzip data from stdin to stdout.

    Reads compressed bytes from stdin, decompresses them using gzip,
    and writes the decompressed bytes to stdout. Operates on raw bytes
    for maximum efficiency and compatibility with all data formats.
    """
    # Read compressed data from stdin (binary mode)
    compressed_data = sys.stdin.buffer.read()

    # Decompress
    try:
        decompressed_data = gzip.decompress(compressed_data)
    except gzip.BadGzipFile as e:
        sys.stderr.write(f"Error: Invalid gzip file: {e}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"Error: Decompression failed: {e}\n")
        sys.exit(1)

    # Write decompressed data to stdout (binary mode)
    sys.stdout.buffer.write(decompressed_data)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gzip decompression plugin")
    parser.add_argument(
        "--mode",
        choices=["raw"],
        required=True,
        help="Operation mode (only 'raw' supported for decompression)"
    )

    args = parser.parse_args()

    if args.mode == "raw":
        decompress_stream()
    else:
        sys.stderr.write(f"Error: Unsupported mode: {args.mode}\n")
        sys.exit(1)
