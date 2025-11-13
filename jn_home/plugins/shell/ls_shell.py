#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = ["^ls($| )", "^ls .*"]
# ///

"""
JN Shell Plugin: ls

Execute `ls` command and convert output to NDJSON.

Usage:
    jn cat ls
    jn cat "ls -l"
    jn cat "ls -la /tmp"
    jn sh ls -l /var/log

Output schema (long format with -l):
    {
        "filename": string,
        "flags": string,
        "links": integer,
        "owner": string,
        "group": string,
        "size": integer,
        "date": string
    }

Output schema (simple format without -l):
    {
        "filename": string
    }
"""

import subprocess
import sys
import json
import shlex
import re


def parse_ls_long_line(line):
    """Parse a single line from ls -l output.

    Example line:
    -rw-r--r-- 1 root root 1234 Nov 13 10:21 file.txt
    drwxr-xr-x 2 user group 4096 Nov 13 10:21 dirname
    lrwxrwxrwx 1 user group 10 Nov 13 10:21 link -> target
    """
    # Match ls -l format
    # flags links owner group size month day time filename
    pattern = r'^([^\s]+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\w+\s+\d+\s+[\d:]+)\s+(.+)$'
    match = re.match(pattern, line)

    if not match:
        return None

    flags, links, owner, group, size, date, filename = match.groups()

    # Handle symlinks (filename might be "link -> target")
    link_to = None
    if ' -> ' in filename:
        filename, link_to = filename.split(' -> ', 1)

    record = {
        "filename": filename,
        "flags": flags,
        "links": int(links),
        "owner": owner,
        "group": group,
        "size": int(size),
        "date": date
    }

    if link_to:
        record["link_to"] = link_to

    return record


def reads(command_str=None):
    """Execute ls command and stream NDJSON records.

    Args:
        command_str: Full command string like "ls -l /tmp" or just "ls"
    """
    if not command_str:
        command_str = "ls"

    # Parse command string into args
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

    # Detect if using long format
    has_long_flag = any(arg.startswith('-') and 'l' in arg for arg in args[1:])

    try:
        # Execute ls command
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

            # Skip empty lines and "total" line
            if not line or line.startswith('total '):
                continue

            if has_long_flag:
                # Parse long format
                record = parse_ls_long_line(line)
                if record:
                    print(json.dumps(record))
            else:
                # Simple format - just filename
                print(json.dumps({"filename": line}))

            sys.stdout.flush()

        # Wait for process
        exit_code = proc.wait()
        if exit_code != 0:
            sys.exit(exit_code)

    except FileNotFoundError:
        error = {"_error": "ls command not found"}
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

    parser = argparse.ArgumentParser(description='JN ls shell plugin')
    parser.add_argument('--mode', default='read', help='Plugin mode (read/write)')
    parser.add_argument('address', nargs='?', help='Command string (e.g., "ls -l /tmp")')

    args = parser.parse_args()

    if args.mode == 'read':
        reads(args.address)
    else:
        error = {"_error": f"Unsupported mode: {args.mode}. Only 'read' supported."}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)
