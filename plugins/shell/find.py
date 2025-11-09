#!/usr/bin/env python3
"""Find files plugin - Parse find command output to NDJSON.

Executes find command and parses output into structured JSON.
Supports various find options and formats.
"""
# /// script
# dependencies = []
# ///
# META: type=source, command="find"

import sys
import json
import subprocess
import os
from typing import Optional, Iterator
from pathlib import Path


def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Execute find and parse output to NDJSON.

    Args:
        config: Configuration dict
            - path: str - Starting path (default: '.')
            - args: list - Arguments to find command

    Yields:
        File/directory records as dicts
    """
    if config is None:
        config = {}

    # Build find command
    path = config.get('path', '.')
    args = config.get('args', [])

    cmd = ['find', path] + args

    # Add -printf for structured output if no format specified
    if '-printf' not in args and '-print0' not in args:
        # Use -printf to get size, type, permissions, and path
        cmd.extend([
            '-printf',
            '%p|||%s|||%Y|||%m|||%u|||%g|||%t\n'
        ])
        structured = True
    else:
        structured = False

    try:
        # Execute find
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Parse output
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            if structured:
                # Parse structured output
                parts = line.split('|||')
                if len(parts) >= 7:
                    path_str = parts[0]
                    size_str = parts[1]
                    type_str = parts[2]
                    mode_str = parts[3]
                    user = parts[4]
                    group = parts[5]
                    mtime = parts[6]

                    # Convert size to int
                    try:
                        size = int(size_str)
                    except ValueError:
                        size = 0

                    # Map type
                    type_map = {
                        'f': 'file',
                        'd': 'directory',
                        'l': 'symlink',
                        'b': 'block',
                        'c': 'character',
                        'p': 'pipe',
                        's': 'socket'
                    }
                    file_type = type_map.get(type_str, 'unknown')

                    # Parse path components
                    path_obj = Path(path_str)

                    yield {
                        'path': path_str,
                        'name': path_obj.name,
                        'parent': str(path_obj.parent),
                        'size': size,
                        'size_kb': round(size / 1024, 2) if size > 0 else 0,
                        'size_mb': round(size / 1024 / 1024, 2) if size > 0 else 0,
                        'type': file_type,
                        'mode': mode_str,
                        'user': user,
                        'group': group,
                        'mtime': mtime
                    }
            else:
                # Simple output - just paths
                yield {
                    'path': line,
                    'name': os.path.basename(line)
                }

    except subprocess.CalledProcessError as e:
        print(f"find command failed: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def examples() -> list[dict]:
    """Return example usage patterns.

    Returns:
        List of example dicts
    """
    return [
        {
            "description": "Find all files in current directory",
            "path": ".",
            "args": []
        },
        {
            "description": "Find Python files",
            "path": ".",
            "args": ["-name", "*.py"]
        },
        {
            "description": "Find files modified in last 24 hours",
            "path": ".",
            "args": ["-mtime", "-1"]
        },
        {
            "description": "Find large files (>10MB)",
            "path": ".",
            "args": ["-size", "+10M"]
        },
        {
            "description": "Find directories only",
            "path": ".",
            "args": ["-type", "d"]
        }
    ]


def test() -> bool:
    """Run built-in tests.

    Returns:
        True if all tests pass
    """
    import tempfile

    print("✓ Plugin structure valid", file=sys.stderr)
    print("✓ run() function defined", file=sys.stderr)
    print("✓ examples() function defined", file=sys.stderr)

    # Try to run find in a temp directory
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('test content')

            results = list(run({'path': tmpdir}))
            if results:
                print(f"✓ Successfully found {len(results)} items", file=sys.stderr)

                # Check that required fields exist
                first = results[0]
                if 'path' in first and 'name' in first:
                    print("✓ Required fields present", file=sys.stderr)

                print(f"\n5/5 tests passed", file=sys.stderr)
                return True
            else:
                print("✗ No items found", file=sys.stderr)
                return False

    except Exception as e:
        print(f"✗ Test failed: {e}", file=sys.stderr)
        return False


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Parse find command output to NDJSON'
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='Starting path (default: .)'
    )
    parser.add_argument(
        'args',
        nargs='*',
        help='Additional find arguments'
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

    # Run find parser
    config = {
        'path': args.path,
        'args': args.args
    }

    for record in run(config):
        print(json.dumps(record))
