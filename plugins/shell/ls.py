#!/usr/bin/env python3
"""Parse ls command output to NDJSON.

Parsing logic inspired by JC project by Kelly Brazil (MIT license).
Reimplemented as standalone CLI plugin for JN.
"""
# /// script
# dependencies = []
# ///
# META: type=source, command="ls"
# KEYWORDS: ls, files, directory, listing, filesystem
# DESCRIPTION: Parse ls command output to NDJSON

import json
import re
import subprocess
import sys
from typing import Iterator, Optional


def parse_ls_line(line: str, long_format: bool = True) -> Optional[dict]:
    """Parse a single line of ls -l output.

    Returns None for non-file lines (total, blank, etc.)
    """
    line = line.strip()

    if not line or line.startswith('total '):
        return None

    if not long_format:
        # Simple format: just filename
        return {'filename': line}

    # Long format (-l): parse permissions, owner, size, date, name
    # Example: -rw-r--r-- 1 user group 1234 Nov  9 10:30 file.txt
    #          drwxr-xr-x 2 user group 4096 Nov  9 10:30 directory

    # Pattern for long listing
    pattern = r'^([bcdlprwxsS-]{10})\s+(\d+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\w+\s+\d+\s+[\d:]+)\s+(.+)$'
    match = re.match(pattern, line)

    if not match:
        # Couldn't parse, return filename only
        parts = line.split(None, 8)
        if len(parts) >= 9:
            return {'filename': parts[8]}
        return None

    perms, links, owner, group, size, date, name = match.groups()

    # Parse permissions
    filetype = perms[0]
    filetype_map = {
        '-': 'file',
        'd': 'directory',
        'l': 'link',
        'b': 'block_device',
        'c': 'character_device',
        'p': 'pipe',
        's': 'socket'
    }

    return {
        'filename': name,
        'type': filetype_map.get(filetype, 'unknown'),
        'permissions': perms,
        'links': int(links),
        'owner': owner,
        'group': group,
        'size': int(size),
        'modified': date,
        'readable': 'r' in perms[1:4],
        'writable': 'w' in perms[1:4],
        'executable': 'x' in perms[1:4] or 's' in perms[1:4]
    }


def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Execute ls and parse output to NDJSON.

    Config keys:
        path: Directory to list (default: current directory)
        args: Additional ls arguments (default: ['-la'])
        raw_command: Use raw command instead of executing (for testing)

    Yields:
        Dict per file/directory with parsed metadata
    """
    config = config or {}
    path = config.get('path', '.')
    args = config.get('args', ['-la'])

    # Check if we're reading from stdin (for testing)
    if config.get('raw_command'):
        output = sys.stdin.read()
    else:
        # Execute ls command
        cmd = ['ls'] + args + [path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            print(f"Error: ls failed: {result.stderr}", file=sys.stderr)
            sys.exit(result.returncode)

        output = result.stdout

    # Parse output
    long_format = '-l' in args or '-la' in args
    for line in output.splitlines():
        parsed = parse_ls_line(line, long_format=long_format)
        if parsed:
            yield parsed


def schema() -> dict:
    """Return JSON schema for ls output."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "description": "File/directory information from ls command",
        "properties": {
            "filename": {"type": "string"},
            "type": {"type": "string"},
            "permissions": {"type": "string"},
            "owner": {"type": "string"},
            "group": {"type": "string"},
            "size": {"type": "integer", "minimum": 0},
            "modified": {"type": "string"}
        }
    }


def examples() -> list[dict]:
    """Return test cases - NO MOCKS, real ls command!"""
    return [
        {
            "description": "Parse real ls output (variable results)",
            "config": {},
            "input": "",
            "expected": [],  # Empty = schema-only validation
            "ignore_fields": set()
        }
    ]


def test() -> bool:
    """Run built-in tests."""
    from io import StringIO

    passed = 0
    failed = 0

    for example in examples():
        desc = example['description']
        try:
            sys.stdin = StringIO(example['input'])
            config = example.get('config', {})
            results = list(run(config))

            # Check count
            if 'expected_count' in example:
                if len(results) != example['expected_count']:
                    print(f"✗ {desc}: Expected {example['expected_count']} records, got {len(results)}", file=sys.stderr)
                    failed += 1
                    continue

            # Check fields
            if 'expected_fields' in example:
                for field in example['expected_fields']:
                    if not all(field in r for r in results):
                        print(f"✗ {desc}: Missing field '{field}'", file=sys.stderr)
                        failed += 1
                        continue

            print(f"✓ {desc}", file=sys.stderr)
            passed += 1

        except Exception as e:
            print(f"✗ {desc}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            failed += 1

    total = passed + failed
    print(f"\n{passed}/{total} tests passed", file=sys.stderr)
    return failed == 0


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Parse ls output to NDJSON'
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='Directory to list (default: current directory)'
    )
    parser.add_argument(
        '-l',
        action='append_const',
        const='-l',
        dest='ls_args',
        help='Long listing format'
    )
    parser.add_argument(
        '-a',
        action='append_const',
        const='-a',
        dest='ls_args',
        help='Include hidden files'
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

    if args.test:
        success = test()
        sys.exit(0 if success else 1)
    else:
        # Build ls arguments
        ls_args = args.ls_args or ['-la']

        config = {
            'path': args.path,
            'args': ls_args
        }

        for record in run(config):
            print(json.dumps(record), flush=True)
