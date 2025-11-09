#!/usr/bin/env python3
"""Parse ps output - NO MOCKS, test real ps command.

Philosophy:
- Run REAL ps command
- No mocks
- Ignore dynamic fields (PIDs, CPU%, memory, timestamps)
- Focus on structure validation
"""
# /// script
# dependencies = []
# ///
# META: type=source

import subprocess
import json
import sys
from typing import Iterator, Optional


def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Parse ps aux output to NDJSON."""
    config = config or {}

    # Run real ps command
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True,
            check=True
        )

        lines = result.stdout.strip().split('\n')
        if len(lines) < 2:
            return

        # Skip header
        for line in lines[1:]:
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue

            yield {
                'user': parts[0],
                'pid': int(parts[1]),
                'cpu_percent': float(parts[2]),
                'mem_percent': float(parts[3]),
                'vsz': int(parts[4]),
                'rss': int(parts[5]),
                'tty': parts[6],
                'stat': parts[7],
                'start': parts[8],
                'time': parts[9],
                'command': parts[10]
            }

    except subprocess.CalledProcessError as e:
        print(f"ps command failed: {e}", file=sys.stderr)
        sys.exit(1)


def schema() -> dict:
    """JSON schema for ps output."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "user": {"type": "string"},
            "pid": {"type": "integer", "minimum": 1},
            "cpu_percent": {"type": "number", "minimum": 0},
            "mem_percent": {"type": "number", "minimum": 0},
            "vsz": {"type": "integer", "minimum": 0},
            "rss": {"type": "integer", "minimum": 0},
            "tty": {"type": "string"},
            "stat": {"type": "string"},
            "start": {"type": "string"},
            "time": {"type": "string"},
            "command": {"type": "string"}
        },
        "required": ["user", "pid", "command"]
    }


def examples() -> list[dict]:
    """Real integration tests - NO MOCKS!

    We run the REAL ps command and check:
    - Schema validates (types, ranges)
    - Structure is correct
    - For commands with variable output, expected can be empty
    - Schema validation ensures fields are correct types
    """
    return [
        {
            "description": "Parse real ps aux output",
            "config": {},
            "input": "",  # Not used - we run real ps
            "expected": [],  # Variable number of processes - schema validates all
            # When expected is empty, tool just validates schema
            "ignore_fields": set()  # Not needed when expected is empty
        }
    ]


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Parse ps output to NDJSON')
    parser.add_argument('--schema', action='store_true', help='Print schema')
    parser.add_argument('--examples', action='store_true', help='Print examples')

    args = parser.parse_args()

    if args.schema:
        print(json.dumps(schema(), indent=2))
        sys.exit(0)

    if args.examples:
        print(json.dumps(examples(), indent=2))
        sys.exit(0)

    for record in run():
        print(json.dumps(record))
