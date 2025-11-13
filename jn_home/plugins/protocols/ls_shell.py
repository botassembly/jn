#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["jc>=1.23.0"]
# [tool.jn]
# matches = ["^ls$", "^ls\\?.*"]
# ///

"""
JN Shell Plugin: ls

Execute `ls` command and convert output to NDJSON using jc parser.

Usage:
    jn cat ls
    jn cat "ls?path=/tmp"
    jn cat "ls?path=/var/log&long=true"
    jn cat "ls?path=/usr/bin" | head -n 10

Supported parameters:
    path - Directory to list (default: current directory)
    long - Use long format (-l) (default: false)
    all - Show hidden files (-a) (default: false)
    recursive - Recursive listing (-R) (default: false)

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
import os
import shutil
from urllib.parse import urlparse, parse_qs


def parse_config_from_url(url=None):
    """Parse configuration from shell:// URL."""
    if not url:
        return {}

    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    # Convert query params to config dict (take first value of each param)
    config = {k: v[0] if v else None for k, v in params.items()}
    return config


def reads(config=None):
    """Execute ls command and stream NDJSON records."""
    if config is None:
        config = {}

    # Parse parameters
    path = config.get('path', '.')
    long_format = config.get('long', 'false').lower() == 'true'
    show_all = config.get('all', 'false').lower() == 'true'
    recursive = config.get('recursive', 'false').lower() == 'true'

    # Validate path exists
    if not os.path.exists(path):
        error = {"_error": f"Path not found: {path}", "path": path}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    # Check if jc is available
    if not shutil.which('jc'):
        error = {"_error": "jc not found. Install: pip install jc", "hint": "https://github.com/kellyjonbrazil/jc"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    # Build ls command
    ls_cmd = ['ls']
    if long_format:
        ls_cmd.append('-l')
    if show_all:
        ls_cmd.append('-a')
    if recursive:
        ls_cmd.append('-R')
    ls_cmd.append(path)

    # Build jc command - use streaming parser if available and long format
    jc_parser = '--ls-s' if long_format else '--ls'
    jc_cmd = ['jc', jc_parser, '-qq']  # -qq: ignore parse errors

    try:
        # Chain: ls | jc
        ls_proc = subprocess.Popen(
            ls_cmd,
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
        if long_format:
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
    parser.add_argument('address', nargs='?', help='Command address with parameters (e.g., ls?path=/tmp)')

    args = parser.parse_args()

    if args.mode == 'read':
        # Parse config from address
        config = {}
        if args.address:
            config = parse_config_from_url(args.address)

        reads(config)
    else:
        error = {"_error": f"Unsupported mode: {args.mode}. Only 'read' supported."}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)
