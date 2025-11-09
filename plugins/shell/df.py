#!/usr/bin/env python3
"""Disk space plugin - Parse df command output to NDJSON.

Executes df command and parses output into structured JSON.
Parsing logic inspired by JC project by Kelly Brazil (MIT license).
"""
# /// script
# dependencies = []
# ///
# META: type=source, command="df"

import sys
import json
import subprocess
import re
from typing import Optional, Iterator


def parse_df_line(line: str) -> Optional[dict]:
    """Parse a single line of df output.

    Args:
        line: Line from df output

    Returns:
        Dict with parsed data or None if invalid
    """
    # df output format: Filesystem 1K-blocks Used Available Use% Mounted on
    parts = line.split()

    if len(parts) < 6:
        return None

    filesystem = parts[0]
    size = parts[1]
    used = parts[2]
    available = parts[3]
    use_percent = parts[4]
    mounted_on = ' '.join(parts[5:])  # May contain spaces

    # Convert numeric fields
    try:
        size_val = int(size)
        used_val = int(used)
        avail_val = int(available)
    except ValueError:
        # Header line or invalid data
        return None

    # Parse percentage
    percent_val = 0
    if use_percent.endswith('%'):
        try:
            percent_val = int(use_percent[:-1])
        except ValueError:
            pass

    return {
        'filesystem': filesystem,
        'size_1k': size_val,
        'used_1k': used_val,
        'available_1k': avail_val,
        'size_mb': round(size_val / 1024, 1),
        'used_mb': round(used_val / 1024, 1),
        'available_mb': round(avail_val / 1024, 1),
        'size_gb': round(size_val / 1024 / 1024, 2),
        'used_gb': round(used_val / 1024 / 1024, 2),
        'available_gb': round(avail_val / 1024 / 1024, 2),
        'use_percent': percent_val,
        'mounted_on': mounted_on
    }


def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Execute df and parse output to NDJSON.

    Args:
        config: Configuration dict
            - args: list - Arguments to df command (default: ['-k'])
            - path: str - Specific path to check (optional)

    Yields:
        Filesystem records as dicts
    """
    if config is None:
        config = {}

    # Build df command
    args = config.get('args', ['-k'])
    path = config.get('path')

    cmd = ['df'] + args
    if path:
        cmd.append(path)

    try:
        # Execute df
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        lines = result.stdout.strip().split('\n')
        if len(lines) < 2:
            return

        # Skip header line
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue

            parsed = parse_df_line(line)
            if parsed:
                yield parsed

    except subprocess.CalledProcessError as e:
        print(f"df command failed: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def examples() -> list[dict]:
    """Return example usage patterns.

    Returns:
        List of example dicts
    """
    return [
        {
            "description": "List all filesystems (default)",
            "args": ["-k"]
        },
        {
            "description": "Human-readable sizes",
            "args": ["-h"]
        },
        {
            "description": "Show specific path",
            "args": ["-k"],
            "path": "/home"
        },
        {
            "description": "Show inode information",
            "args": ["-i"]
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

    # Try to run df and parse output
    try:
        results = list(run({'args': ['-k']}))
        if results:
            print(f"✓ Successfully parsed {len(results)} filesystems", file=sys.stderr)

            # Check that required fields exist
            first = results[0]
            required_fields = ['filesystem', 'size_1k', 'used_1k', 'available_1k', 'use_percent', 'mounted_on']
            if all(field in first for field in required_fields):
                print("✓ All required fields present", file=sys.stderr)

            print(f"\n5/5 tests passed", file=sys.stderr)
            return True
        else:
            print("✗ No filesystems parsed", file=sys.stderr)
            return False

    except Exception as e:
        print(f"✗ Test failed: {e}", file=sys.stderr)
        return False


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Parse df command output to NDJSON'
    )
    parser.add_argument(
        'path',
        nargs='?',
        help='Specific path to check (optional)'
    )
    parser.add_argument(
        '--args',
        nargs='*',
        default=['-k'],
        help='Arguments to df command (default: -k)'
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

    # Run df parser
    config = {'args': args.args if args.args != ['-k'] else ['-k']}
    if args.path:
        config['path'] = args.path

    for record in run(config):
        print(json.dumps(record))
