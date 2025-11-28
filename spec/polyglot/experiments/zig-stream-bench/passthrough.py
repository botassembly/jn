#!/usr/bin/env python3
"""Simple stdin→stdout passthrough for benchmarking."""

import sys

def main():
    # Buffered line-by-line passthrough
    for line in sys.stdin:
        sys.stdout.write(line)

if __name__ == "__main__":
    main()
