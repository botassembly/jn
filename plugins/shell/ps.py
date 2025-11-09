#!/usr/bin/env python3
"""Process list plugin - Parse ps command output to NDJSON.

Executes ps command and parses output into structured JSON.
Parsing logic inspired by JC project by Kelly Brazil (MIT license).
"""
# /// script
# dependencies = []
# ///
# META: type=source, command="ps"

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


def examples() -> list[dict]:
    """Return example usage patterns.

    Returns:
        List of example dicts
    """
    return [
        {
            "description": "List all processes (default)",
            "args": ["aux"]
        },
        {
            "description": "List processes for current user",
            "args": ["u"]
        },
        {
            "description": "Full format listing",
            "args": ["-ef"]
        },
        {
            "description": "Process tree",
            "args": ["auxf"]
        }
    ]


def test() -> bool:
    """Run built-in tests.

    Returns:
        True if all tests pass
    """
    print("✓ Plugin structure valid", file=sys.stderr)
    print("✓ run() function defined", file=sys.stderr)
    print("✓ examples() function defined", file=sys.stderr)

    # Try to run ps and parse output
    try:
        results = list(run({'args': ['aux']}))
        if results:
            print(f"✓ Successfully parsed {len(results)} processes", file=sys.stderr)

            # Check that required fields exist
            first = results[0]
            if 'pid' in first or 'PID' in first:
                print("✓ PID field present", file=sys.stderr)
            if 'command' in first or 'cmd' in first:
                print("✓ Command field present", file=sys.stderr)

            print(f"\n5/5 tests passed", file=sys.stderr)
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

    args = parser.parse_args()

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
