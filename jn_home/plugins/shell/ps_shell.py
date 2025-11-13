#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["jc>=1.23.0"]
# [tool.jn]
# matches = ["^ps($| )", "^ps .*"]
# ///

"""
JN Shell Plugin: ps

Execute `ps` command and convert output to NDJSON using jc parser.

Usage:
    jn cat ps
    jn cat "ps aux"
    jn cat "ps -ef"
    jn sh ps aux
    jn sh ps -ef | jn filter '.cpu_percent > 50'

The command can be any valid ps invocation.

Output schema:
    {
        "pid": integer,
        "ppid": integer,
        "user": string,
        "cpu_percent": float,
        "mem_percent": float,
        "vsz": integer,
        "rss": integer,
        "tty": string,
        "stat": string,
        "start": string,
        "time": string,
        "command": string
    }
"""

import subprocess
import sys
import json
import shutil
import shlex


def reads(command_str=None):
    """Execute ps command and stream NDJSON records.

    Args:
        command_str: Full command string like "ps aux" or just "ps"
    """
    if not command_str:
        command_str = "ps"

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

    if not args or args[0] != 'ps':
        error = {"_error": f"Expected ps command, got: {command_str}"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    # Build jc command
    jc_cmd = ['jc', '--ps']

    try:
        # Chain: ps [args] | jc
        ps_proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=sys.stderr
        )

        jc_proc = subprocess.Popen(
            jc_cmd,
            stdin=ps_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True
        )

        # CRITICAL: Close ps stdout in parent to enable SIGPIPE propagation
        ps_proc.stdout.close()

        # Read jc output (JSON array)
        output = jc_proc.stdout.read()

        # Wait for both processes
        jc_exit = jc_proc.wait()
        ps_exit = ps_proc.wait()

        # Convert JSON array to NDJSON
        try:
            records = json.loads(output) if output.strip() else []
            for record in records:
                print(json.dumps(record))
        except json.JSONDecodeError as e:
            error = {"_error": f"Failed to parse jc output: {e}"}
            print(json.dumps(error), file=sys.stderr)
            sys.exit(1)

        # Exit with error if either command failed
        if jc_exit != 0:
            sys.exit(jc_exit)
        if ps_exit != 0:
            sys.exit(ps_exit)

    except FileNotFoundError as e:
        error = {"_error": f"Command not found: {e}"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)
    except BrokenPipeError:
        # Downstream closed pipe (e.g., head -n 10)
        pass
    except KeyboardInterrupt:
        # User interrupted
        pass


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='JN ps shell plugin')
    parser.add_argument('--mode', default='read', help='Plugin mode (read/write)')
    parser.add_argument('address', nargs='?', help='Command string (e.g., "ps aux")')

    args = parser.parse_args()

    if args.mode == 'read':
        reads(args.address)
    else:
        error = {"_error": f"Unsupported mode: {args.mode}. Only 'read' supported."}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)
