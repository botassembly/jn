#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = ["^find($| )", "^find .*"]
# ///

"""
JN Shell Plugin: find

Execute `find` command and convert output to NDJSON.

Usage:
    jn cat find
    jn cat "find ."
    jn cat "find /tmp -name '*.py'"
    jn sh find . -type f -name "*.log"
    jn sh find /var -size +1M

Output schema:
    {
        "path": string
    }
"""

import subprocess
import sys
import json
import shlex
import os


def reads(command_str=None):
    """Execute find command and stream NDJSON records.

    Args:
        command_str: Full command string like "find . -name '*.py'" or just "find"
    """
    if not command_str:
        command_str = "find ."

    # Parse command string into args
    try:
        args = shlex.split(command_str)
    except ValueError as e:
        error = {"_error": f"Invalid command syntax: {e}"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    if not args or args[0] != 'find':
        error = {"_error": f"Expected find command, got: {command_str}"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    try:
        # Execute find command
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # Capture stderr to ignore permission errors
            text=True,
            bufsize=1  # Line buffered
        )

        # Stream output line-by-line
        for line in proc.stdout:
            line = line.rstrip()

            # Skip empty lines
            if not line:
                continue

            # Simple format: just the path
            record = {"path": line}
            print(json.dumps(record))
            sys.stdout.flush()

        # Wait for process
        # Note: find returns non-zero on permission errors, but we still output successful results
        proc.wait()

    except FileNotFoundError:
        error = {"_error": "find command not found"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)
    except BrokenPipeError:
        # Downstream closed pipe
        pass
    except KeyboardInterrupt:
        # User interrupted
        pass


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='JN find shell plugin')
    parser.add_argument('--mode', default='read', help='Plugin mode (read/write)')
    parser.add_argument('address', nargs='?', help='Command string (e.g., "find . -name \'*.py\'")')

    args = parser.parse_args()

    if args.mode == 'read':
        reads(args.address)
    else:
        error = {"_error": f"Unsupported mode: {args.mode}. Only 'read' supported."}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)
