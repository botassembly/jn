#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = ["^ps($| )", "^ps .*"]
# ///

"""
JN Shell Plugin: ps

Execute `ps` command and convert output to NDJSON.

Usage:
    jn cat ps
    jn cat "ps aux"
    jn cat "ps -ef"
    jn sh ps aux
    jn sh ps -ef | jn filter '.cpu_percent > 50'

Output schema (ps aux format):
    {
        "user": string,
        "pid": integer,
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
import shlex
import re


def parse_ps_aux_line(line):
    """Parse a single line from ps aux output.

    Example line:
    root         1  0.0  0.1 169104 13640 ?        Ss   Nov07   0:11 /sbin/init
    """
    # PS aux format: USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND
    parts = line.split(None, 10)  # Split on whitespace, max 11 parts

    if len(parts) < 11:
        return None

    try:
        record = {
            "user": parts[0],
            "pid": int(parts[1]),
            "cpu_percent": float(parts[2]),
            "mem_percent": float(parts[3]),
            "vsz": int(parts[4]),
            "rss": int(parts[5]),
            "tty": parts[6] if parts[6] != '?' else None,
            "stat": parts[7],
            "start": parts[8],
            "time": parts[9],
            "command": parts[10]
        }
        return record
    except (ValueError, IndexError):
        return None


def parse_ps_ef_line(line):
    """Parse a single line from ps -ef output.

    Example line:
    root         1     0  0 Nov07 ?        00:00:11 /sbin/init
    """
    # PS -ef format: UID PID PPID C STIME TTY TIME CMD
    parts = line.split(None, 7)  # Split on whitespace, max 8 parts

    if len(parts) < 8:
        return None

    try:
        record = {
            "user": parts[0],
            "pid": int(parts[1]),
            "ppid": int(parts[2]),
            "c": int(parts[3]),
            "stime": parts[4],
            "tty": parts[5] if parts[5] != '?' else None,
            "time": parts[6],
            "command": parts[7]
        }
        return record
    except (ValueError, IndexError):
        return None


def reads(command_str=None):
    """Execute ps command and stream NDJSON records.

    Args:
        command_str: Full command string like "ps aux" or just "ps"
    """
    if not command_str:
        command_str = "ps"

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

    # Detect format (aux vs -ef)
    has_aux = 'aux' in ' '.join(args[1:])
    has_ef = '-ef' in ' '.join(args[1:]) or '-e' in args[1:] and '-f' in args[1:]

    try:
        # Execute ps command
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1  # Line buffered
        )

        # Stream output line-by-line
        first_line = True
        for line in proc.stdout:
            line = line.rstrip()

            # Skip empty lines and header
            if not line or first_line:
                first_line = False
                continue

            # Parse based on format
            if has_aux:
                record = parse_ps_aux_line(line)
            elif has_ef:
                record = parse_ps_ef_line(line)
            else:
                # Default to aux parser
                record = parse_ps_aux_line(line)

            if record:
                print(json.dumps(record))
                sys.stdout.flush()

        # Wait for process
        exit_code = proc.wait()
        if exit_code != 0:
            sys.exit(exit_code)

    except FileNotFoundError:
        error = {"_error": "ps command not found"}
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
