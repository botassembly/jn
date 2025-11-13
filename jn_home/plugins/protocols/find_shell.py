#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["jc>=1.23.0"]
# [tool.jn]
# matches = ["^shell://find$", "^shell://find\\?.*"]
# ///

"""
JN Shell Plugin: find

Execute `find` command and convert output to NDJSON using jc parser.

Usage:
    jn cat shell://find
    jn cat "shell://find?path=/tmp"
    jn cat "shell://find?path=/home&name=*.py"
    jn cat "shell://find?path=/var&type=f&name=*.log" | jn filter '.size > 1000000'

Supported parameters:
    path - Starting directory (default: current directory)
    name - File name pattern (e.g., "*.py")
    type - File type: f (file), d (directory), l (symlink)
    maxdepth - Maximum depth to descend
    mindepth - Minimum depth to descend
    size - Size filter (e.g., "+1M", "-100k")
    mtime - Modified time (e.g., "-7" for last 7 days)

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
    """Execute find command and stream NDJSON records."""
    if config is None:
        config = {}

    # Parse parameters
    path = config.get('path', '.')
    name = config.get('name')
    file_type = config.get('type')
    maxdepth = config.get('maxdepth')
    mindepth = config.get('mindepth')
    size = config.get('size')
    mtime = config.get('mtime')

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

    # Build find command
    find_cmd = ['find', path]

    # Add optional parameters
    if maxdepth:
        find_cmd.extend(['-maxdepth', maxdepth])
    if mindepth:
        find_cmd.extend(['-mindepth', mindepth])
    if file_type:
        find_cmd.extend(['-type', file_type])
    if name:
        find_cmd.extend(['-name', name])
    if size:
        find_cmd.extend(['-size', size])
    if mtime:
        find_cmd.extend(['-mtime', mtime])

    # Build jc command
    jc_cmd = ['jc', '--find']

    try:
        # Chain: find | jc
        find_proc = subprocess.Popen(
            find_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        jc_proc = subprocess.Popen(
            jc_cmd,
            stdin=find_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # CRITICAL: Close find stdout in parent to enable SIGPIPE propagation
        find_proc.stdout.close()

        # Capture stderr from find (for permission denied errors)
        # We'll merge them with the jc output
        import threading
        find_errors = []

        def read_find_stderr():
            for line in find_proc.stderr:
                # Parse find errors like "find: './inaccessible': Permission denied"
                error_record = {
                    "path": None,
                    "node": None,
                    "error": line.strip()
                }
                find_errors.append(error_record)

        stderr_thread = threading.Thread(target=read_find_stderr, daemon=True)
        stderr_thread.start()

        # Read jc output (JSON array)
        output = jc_proc.stdout.read()

        # Wait for both processes
        jc_exit = jc_proc.wait()
        find_exit = find_proc.wait()
        stderr_thread.join(timeout=0.5)

        # Parse and output results
        try:
            records = json.loads(output) if output.strip() else []

            # Output all successful records
            for record in records:
                print(json.dumps(record))

            # Output error records
            for error_record in find_errors:
                print(json.dumps(error_record))

        except json.JSONDecodeError as e:
            error = {"_error": f"Failed to parse jc output: {e}", "output": output[:200]}
            print(json.dumps(error), file=sys.stderr)
            sys.exit(1)

        # Note: find returns non-zero if it encounters errors (permission denied, etc.)
        # but we still want to process successful results, so we don't exit(find_exit)

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
    parser.add_argument('--url', help='Shell URL with parameters')
    parser.add_argument('--config', help='JSON config string')

    args = parser.parse_args()

    if args.mode == 'read':
        # Parse config from URL or config arg
        config = {}
        if args.url:
            config = parse_config_from_url(args.url)
        elif args.config:
            config = json.loads(args.config)

        reads(config)
    else:
        error = {"_error": f"Unsupported mode: {args.mode}. Only 'read' supported."}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)
