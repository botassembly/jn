#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["jc>=1.23.0"]
# [tool.jn]
# matches = ["^shell://ps$", "^shell://ps\\?.*"]
# ///

"""
JN Shell Plugin: ps

Execute `ps` command and convert output to NDJSON using jc parser.

Usage:
    jn cat shell://ps
    jn cat "shell://ps?full=true"
    jn cat "shell://ps?user=root"
    jn cat shell://ps | jn filter '.cpu_percent > 50'
    jn cat shell://ps | jn filter '.cmd | contains("python")'

Supported parameters:
    full - Use full format (ps -ef or ps aux) (default: true)
    user - Filter by user (ps -u <user>)
    pid - Filter by PID (ps -p <pid>)

Output schema:
    {
        "uid": string,          # User ID
        "pid": integer,         # Process ID
        "ppid": integer,        # Parent process ID
        "c": integer,           # CPU utilization
        "stime": string,        # Start time
        "tty": string,          # Terminal (null if none)
        "time": string,         # Cumulative CPU time
        "cmd": string,          # Command
        "user": string,         # Username
        "cpu_percent": float,   # CPU percentage
        "mem_percent": float,   # Memory percentage
        "vsz": integer,         # Virtual memory size (KB)
        "rss": integer,         # Resident set size (KB)
        "stat": string,         # Process state
        "start": string,        # Start time
        "command": string       # Full command line
    }

Note: Fields vary depending on ps options and platform.
"""

import subprocess
import sys
import json
import shutil
import platform
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
    """Execute ps command and stream NDJSON records."""
    if config is None:
        config = {}

    # Parse parameters
    full_format = config.get('full', 'true').lower() == 'true'
    user = config.get('user')
    pid = config.get('pid')

    # Check if jc is available
    if not shutil.which('jc'):
        error = {"_error": "jc not found. Install: pip install jc", "hint": "https://github.com/kellyjonbrazil/jc"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    # Build ps command (platform-aware)
    ps_cmd = ['ps']

    if full_format:
        # Use different options based on platform
        system = platform.system()
        if system in ['Linux', 'Windows']:  # Windows with WSL
            ps_cmd.append('-ef')
        else:  # macOS, BSD
            ps_cmd.append('aux')

    if user:
        ps_cmd.extend(['-u', user])

    if pid:
        ps_cmd.extend(['-p', pid])

    # Build jc command
    jc_cmd = ['jc', '--ps']

    try:
        # Chain: ps | jc
        ps_proc = subprocess.Popen(
            ps_cmd,
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

        # Parse and output results as NDJSON
        try:
            records = json.loads(output) if output.strip() else []
            for record in records:
                print(json.dumps(record))
        except json.JSONDecodeError as e:
            error = {"_error": f"Failed to parse jc output: {e}", "output": output[:200]}
            print(json.dumps(error), file=sys.stderr)
            sys.exit(1)

        # Exit with error if commands failed
        if jc_exit != 0:
            sys.exit(jc_exit)
        if ps_exit != 0:
            sys.exit(ps_exit)

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

    parser = argparse.ArgumentParser(description='JN ps shell plugin')
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
