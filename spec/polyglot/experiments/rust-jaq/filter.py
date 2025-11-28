#!/usr/bin/env python3
"""Python + jq filter for benchmark comparison."""

import subprocess
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: filter.py <jq-expression>", file=sys.stderr)
        sys.exit(1)

    expr = sys.argv[1]

    # Run jq as subprocess
    proc = subprocess.Popen(
        ["jq", "-c", expr],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    proc.wait()
    sys.exit(proc.returncode)

if __name__ == "__main__":
    main()
