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
import os
import sys


def safe_write_bytes(data: bytes) -> None:
    """Write bytes to stdout.buffer safely, exit on EPIPE."""
    try:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    except BrokenPipeError:
        os._exit(0)


def decompress_stream():
    """Stream gzip decompression from stdin to stdout.

    - Reads compressed bytes from stdin
    - Decompresses in fixed-size chunks (constant memory)
    - Writes decompressed bytes to stdout
    - Exits cleanly on BrokenPipeError (downstream closed)
    """
    try:
        with gzip.GzipFile(fileobj=sys.stdin.buffer, mode="rb") as gz:
            while True:
                chunk = gz.read(8192)
                if not chunk:
                    break
                safe_write_bytes(chunk)
    except gzip.BadGzipFile as e:
        sys.stderr.write(f"Error: Invalid gzip file: {e}\n")
        sys.exit(1)
    except BrokenPipeError:
        # Downstream closed while reading - normal termination
        os._exit(0)
    except Exception as e:
        sys.stderr.write(f"Error: Decompression failed: {e}\n")
        sys.exit(1)


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
