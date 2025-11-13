#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["jc>=1.23.0"]
# [tool.jn]
# matches = ["^ls($| )", "^ls .*"]
# ///

"""
JN Shell Plugin: ls

Execute `ls` command and convert output to NDJSON using jc parser.

Usage:
    jn cat ls
    jn cat "ls -l"
    jn cat "ls -la /tmp"
    jn sh ls -l /var/log

The command can be any valid ls invocation with flags and paths.

Output schema (long format):
    {
        "filename": string,
        "flags": string,          # e.g. "drwxr-xr-x"
        "links": integer,
        "owner": string,
        "group": string,
        "size": integer,
        "date": string,
        "link_to": string         # for symlinks
    }

Output schema (simple format):
    {
        "filename": string
    }
"""

import subprocess
import sys
import json
import shutil
import shlex


def reads(command_str=None):
    """Execute ls command and stream NDJSON records.

    Args:
        command_str: Full command string like "ls -l /tmp" or just "ls"
    """
    if not command_str:
        command_str = "ls"

    # Check if jc is available
    if not shutil.which('jc'):
        error = {"_error": "jc not found. Install: pip install jc", "hint": "https://github.com/kellyjonbrazil/jc"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    # Parse command string into args using shell lexer
    try:
        args = shlex.split(command_str)
    except ValueError as e:
        error = {"_error": f"Invalid command syntax: {e}"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    if not args or args[0] != 'ls':
        error = {"_error": f"Expected ls command, got: {command_str}"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    # Detect if using long format (for choosing jc parser)
    has_long_flag = any(arg.startswith('-') and 'l' in arg for arg in args[1:])

    # Build jc command - use streaming parser if long format
    jc_parser = '--ls-s' if has_long_flag else '--ls'
    jc_cmd = ['jc', jc_parser, '-qq']  # -qq: ignore parse errors

    try:
        # Chain: ls [args] | jc
        ls_proc = subprocess.Popen(
            args,  # Use parsed args
            stdout=subprocess.PIPE,
            stderr=sys.stderr
        )

        jc_proc = subprocess.Popen(
            jc_cmd,
            stdin=ls_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1  # Line buffered
        )

        # CRITICAL: Close ls stdout in parent to enable SIGPIPE propagation
        ls_proc.stdout.close()

        # Stream output line-by-line (NDJSON from jc --ls-s)
        if has_long_flag:
            # Streaming parser outputs NDJSON (one object per line)
            for line in jc_proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
        else:
            # Non-streaming parser outputs JSON array
            output = jc_proc.stdout.read()
            try:
                records = json.loads(output)
                for record in records:
                    print(json.dumps(record))
            except json.JSONDecodeError as e:
                error = {"_error": f"Failed to parse jc output: {e}"}
                print(json.dumps(error), file=sys.stderr)
                sys.exit(1)

        # Wait for both processes
        jc_exit = jc_proc.wait()
        ls_exit = ls_proc.wait()

        # Exit with error if either command failed
        if jc_exit != 0:
            sys.exit(jc_exit)
        if ls_exit != 0:
            sys.exit(ls_exit)

    except FileNotFoundError as e:
        error = {"_error": f"Command not found: {e}"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)
    except BrokenPipeError:
        # Downstream closed pipe (e.g., head -n 10)
        # This is expected, exit gracefully
        pass
    except KeyboardInterrupt:
        # User interrupted
        pass


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='JN ls shell plugin')
    parser.add_argument('--mode', default='read', help='Plugin mode (read/write)')
    parser.add_argument('address', nargs='?', help='Command string (e.g., "ls -l /tmp")')

    args = parser.parse_args()

    if args.mode == 'read':
        # Pass full command string to reads()
        reads(args.address)
    else:
        error = {"_error": f"Unsupported mode: {args.mode}. Only 'read' supported."}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)
