#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = ["^env($| )", "^env .*"]
# ///

"""
JN Shell Plugin: env

Execute `env` command to list environment variables as NDJSON.

Usage:
    jn cat env
    jn sh env
    jn sh env | jn filter '.name == "PATH"'
    jn sh env | jn filter '.value | contains("/usr/local")'

Output schema:
    {
        "name": string,
        "value": string
    }
"""

import subprocess
import sys
import json
import shlex


def reads(command_str=None):
    """Execute env command and stream NDJSON records.

    Args:
        command_str: Full command string like "env" (rarely needs args)
    """
    if not command_str:
        command_str = "env"

    # Parse command string into args
    try:
        args = shlex.split(command_str)
    except ValueError as e:
        error = {"_error": f"Invalid command syntax: {e}"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    if not args or args[0] != 'env':
        error = {"_error": f"Expected env command, got: {command_str}"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    try:
        # Execute env command
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1  # Line buffered
        )

        # Stream output line-by-line
        for line in proc.stdout:
            line = line.rstrip()

            # Skip empty lines
            if not line:
                continue

            # Parse NAME=VALUE format
            if '=' in line:
                name, value = line.split('=', 1)
                record = {
                    "name": name,
                    "value": value
                }
                print(json.dumps(record))
                sys.stdout.flush()

        # Wait for process
        exit_code = proc.wait()
        if exit_code != 0:
            sys.exit(exit_code)

    except FileNotFoundError:
        error = {"_error": "env command not found"}
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

    parser = argparse.ArgumentParser(description='JN env shell plugin')
    parser.add_argument('--mode', default='read', help='Plugin mode (read/write)')
    parser.add_argument('address', nargs='?', help='Command string (e.g., "env")')

    args = parser.parse_args()

    if args.mode == 'read':
        reads(args.address)
    else:
        error = {"_error": f"Unsupported mode: {args.mode}. Only 'read' supported."}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)
