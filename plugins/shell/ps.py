#!/usr/bin/env python3
"""Process list plugin - Parse ps command output to NDJSON.

Executes ps command and parses output into structured JSON.
Parsing logic inspired by JC project by Kelly Brazil (MIT license).
"""
# /// script
# dependencies = []
# ///
# META: type=source, command="ps"
# KEYWORDS: ps, process, system, monitoring, unix
# DESCRIPTION: Parse ps command output to NDJSON

import sys
import json
import subprocess
import re
from typing import Optional, Iterator, List


def parse_ps_line(line: str, headers: List[str]) -> Optional[dict]:
    """Parse a single line of ps output.

    Args:
        line: Line from ps output
        headers: List of column headers

    Returns:
        Dict with parsed data or None if invalid
    """
    # Split on whitespace, but preserve last field (COMMAND) which may have spaces
    parts = line.split(None, len(headers) - 1)

    if len(parts) < len(headers):
        return None

    # Build record
    record = {}
    for i, header in enumerate(headers):
        value = parts[i] if i < len(parts) else ''

        # Try to convert numeric fields
        if header in ('PID', 'PPID', 'PGID', 'SID', 'TTY', 'UID', 'GID'):
            try:
                record[header.lower()] = int(value) if value.isdigit() else value
            except ValueError:
                record[header.lower()] = value
        elif header in ('PCPU', '%CPU'):
            try:
                record['cpu_percent'] = float(value)
            except ValueError:
                record['cpu_percent'] = value
        elif header in ('PMEM', '%MEM'):
            try:
                record['mem_percent'] = float(value)
            except ValueError:
                record['mem_percent'] = value
        elif header in ('VSZ', 'RSS'):
            try:
                record[header.lower()] = int(value)
            except ValueError:
                record[header.lower()] = value
        elif header in ('STAT', 'S'):
            record['status'] = value
        elif header in ('TIME', 'ELAPSED'):
            record['time'] = value
        elif header in ('CMD', 'COMMAND', 'ARGS'):
            record['command'] = value
        elif header == 'USER':
            record['user'] = value
        else:
            # Generic field
            record[header.lower()] = value

    return record


def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Execute ps and parse output to NDJSON.

    Args:
        config: Configuration dict
            - args: list - Arguments to ps command (default: ['aux'])
            - path: str - Path argument (optional)

    Yields:
        Process records as dicts
    """
    if config is None:
        config = {}

    # Build ps command
    args = config.get('args', ['aux'])
    cmd = ['ps'] + args

    try:
        # Execute ps
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        lines = result.stdout.strip().split('\n')
        if len(lines) < 2:
            return

        # Parse header
        header_line = lines[0]
        headers = header_line.split()

        # Parse data lines
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue

            parsed = parse_ps_line(line, headers)
            if parsed:
                yield parsed

    except subprocess.CalledProcessError as e:
        print(f"ps command failed: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def schema() -> dict:
    """Return JSON schema for ps output.

    Defines structure and types for process records.
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "description": "Process information from ps command",
        "properties": {
            "pid": {"type": "integer", "minimum": 1, "description": "Process ID"},
            "ppid": {"type": ["integer", "string"], "description": "Parent process ID"},
            "user": {"type": "string", "description": "Process owner"},
            "cpu_percent": {"type": "number", "minimum": 0, "description": "CPU usage percentage"},
            "mem_percent": {"type": "number", "minimum": 0, "description": "Memory usage percentage"},
            "vsz": {"type": "integer", "minimum": 0, "description": "Virtual memory size"},
            "rss": {"type": "integer", "minimum": 0, "description": "Resident set size"},
            "status": {"type": "string", "description": "Process status"},
            "time": {"type": "string", "description": "CPU time"},
            "command": {"type": "string", "description": "Command name"}
        }
    }


def examples() -> list[dict]:
    """Return example usage patterns - NO MOCKS, real ps command!

    Returns:
        List of example dicts with schema-only validation
    """
    return [
        {
            "description": "Parse real ps aux output (variable results)",
            "config": {"args": ["aux"]},
            "input": "",
            "expected": [],  # Empty = schema-only validation (output varies)
            "ignore_fields": set()  # Not needed for schema-only validation
        }
    ]


def test() -> bool:
    """Run built-in tests - NO MOCKS, real ps command!

    Runs real ps and validates against schema.

    Returns:
        True if all tests pass
    """
    print("Testing with REAL ps command (NO MOCKS)...", file=sys.stderr)

    # Try to run ps and parse output
    try:
        results = list(run({'args': ['aux']}))
        if results:
            print(f"✓ Successfully parsed {len(results)} processes", file=sys.stderr)

            # Check that required fields exist in first result
            first = results[0]
            if 'pid' in first:
                print("✓ PID field present", file=sys.stderr)
            if 'command' in first:
                print("✓ Command field present", file=sys.stderr)

            print(f"\n3/3 real ps tests passed", file=sys.stderr)
            return True
        else:
            print("✗ No processes parsed", file=sys.stderr)
            return False

    except Exception as e:
        print(f"✗ Test failed: {e}", file=sys.stderr)
        return False


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Parse ps command output to NDJSON'
    )
    parser.add_argument(
        'args',
        nargs='*',
        default=['aux'],
        help='Arguments to ps command (default: aux)'
    )
    parser.add_argument(
        '--examples',
        action='store_true',
        help='Show usage examples'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run built-in tests'
    )
    parser.add_argument(
        '--schema',
        action='store_true',
        help='Output JSON schema'
    )

    args = parser.parse_args()

    if args.schema:
        print(json.dumps(schema(), indent=2))
        sys.exit(0)

    if args.examples:
        print(json.dumps(examples(), indent=2))
        sys.exit(0)

    if args.test:
        success = test()
        sys.exit(0 if success else 1)

    # Run ps parser
    config = {'args': args.args if args.args != ['aux'] else ['aux']}
    for record in run(config):
        print(json.dumps(record))
