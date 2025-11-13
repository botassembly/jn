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

CHUNK_SIZE = 64 * 1024


def decompress_stream():
    """Decompress gzip data from stdin to stdout.

    Streams decompressed bytes so upstream/downstream tools can stop early.
    Broken pipes are expected when downstream commands (like sampling analyzers)
    finish before the entire stream is consumed, so we swallow them quietly.
    """

    try:
        gz_stream = gzip.GzipFile(fileobj=sys.stdin.buffer)
    except gzip.BadGzipFile as e:
        sys.stderr.write(f"Error: Invalid gzip file: {e}\n")
        sys.exit(1)

    try:
        with gz_stream:
            while True:
                chunk = gz_stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                try:
                    sys.stdout.buffer.write(chunk)
                except BrokenPipeError:
                    # Downstream stopped reading (e.g., limit reached)
                    return
    except BrokenPipeError:
        # Downstream stopped during read/write
        return
    except Exception as e:
        sys.stderr.write(f"Error: Decompression failed: {e}\n")
        sys.exit(1)

    try:
        sys.stdout.buffer.flush()
    except BrokenPipeError:
        pass


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
