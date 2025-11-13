#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["jc>=1.23.0"]
# [tool.jn]
# matches = ["^find($| )", "^find .*"]
# ///

"""
JN Shell Plugin: find

Execute `find` command and convert output to NDJSON using jc parser.

Usage:
    jn cat find
    jn cat "find ."
    jn cat "find /tmp -name '*.py'"
    jn sh find . -type f -name "*.log"
    jn sh find /var -size +1M | jn filter '.size > 1000000'

The command can be any valid find invocation.

Output schema:
    {
        "path": string,         # Directory path
        "node": string,         # File/directory name
        "error": string         # If permission denied, etc.
    }

Note: find outputs paths naturally as it discovers them, so streaming
      behavior is excellent even without jc streaming parser.
"""

import subprocess
import sys
import json
import shutil
import shlex


def reads(command_str=None):
    """Execute find command and stream NDJSON records.

    Args:
        command_str: Full command string like "find . -name '*.py'" or just "find"
    """
    if not command_str:
        command_str = "find ."

    # Check if jc is available
    if not shutil.which('jc'):
        error = {"_error": "jc not found. Install: pip install jc", "hint": "https://github.com/kellyjonbrazil/jc"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

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

    # Build jc command
    jc_cmd = ['jc', '--find']

    try:
        # Chain: find [args] | jc
        find_proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        jc_proc = subprocess.Popen(
            jc_cmd,
            stdin=find_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True
        )

        # CRITICAL: Close find stdout in parent to enable SIGPIPE propagation
        find_proc.stdout.close()

        # Read jc output (JSON array)
        output = jc_proc.stdout.read()

        # Wait for both processes
        jc_exit = jc_proc.wait()
        find_exit = find_proc.wait()

        # Convert JSON array to NDJSON
        try:
            records = json.loads(output) if output.strip() else []
            for record in records:
                print(json.dumps(record))
        except json.JSONDecodeError as e:
            error = {"_error": f"Failed to parse jc output: {e}"}
            print(json.dumps(error), file=sys.stderr)
            sys.exit(1)

        # Note: find returns non-zero if it encounters errors (permission denied, etc.)
        # but we still output successful results. Only exit on jc errors.
        if jc_exit != 0:
            sys.exit(jc_exit)

    except FileNotFoundError as e:
        error = {"_error": f"Command not found: {e}"}
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
