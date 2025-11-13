#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = ["^shell://tail$", "^shell://tail\\?.*"]
# ///

"""
JN Shell Plugin: tail

Execute `tail` command to stream file contents, with optional follow mode.

Usage:
    jn cat "shell://tail?path=/var/log/syslog"
    jn cat "shell://tail?path=/var/log/app.log&follow=true"
    jn cat "shell://tail?path=/var/log/app.log&lines=50"
    jn cat "shell://tail?path=/var/log/app.log&follow=true" | jn filter '.level == "ERROR"'

Supported parameters:
    path - File to tail (required)
    follow - Follow file as it grows (-F flag) (default: false)
    lines - Number of lines to show initially (default: 10)

Output schema:
    {
        "line": string,         # The log line
        "path": string,         # Source file path
        "line_number": integer  # Sequential line number (1-based)
    }

Follow mode notes:
    - Runs indefinitely until interrupted (Ctrl+C) or pipe closed
    - Uses `tail -F` which handles log rotation
    - Backpressure automatic: if downstream slow, tail blocks
    - Memory constant regardless of file size or growth rate
"""

import subprocess
import sys
import json
import os
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
    """Stream file contents using tail, optionally following."""
    if config is None:
        config = {}

    # Parse parameters
    path = config.get('path')
    if not path:
        error = {"_error": "Missing required parameter: path"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    follow = config.get('follow', 'false').lower() == 'true'
    lines = config.get('lines', '10')

    # Validate path exists (unless follow mode, where file might be created later)
    if not follow and not os.path.exists(path):
        error = {"_error": f"File not found: {path}", "path": path}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    # Build tail command
    tail_cmd = ['tail']
    if follow:
        # -F: follow by name, handle log rotation
        tail_cmd.extend(['-F', '-n', lines])
    else:
        tail_cmd.extend(['-n', lines])
    tail_cmd.append(path)

    try:
        # Spawn tail process
        proc = subprocess.Popen(
            tail_cmd,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1  # Line buffered
        )

        # Stream output line-by-line
        line_number = 0
        for line in proc.stdout:
            line_number += 1
            record = {
                "line": line.rstrip(),
                "path": path,
                "line_number": line_number
            }
            print(json.dumps(record))
            sys.stdout.flush()

    except FileNotFoundError:
        error = {"_error": "tail command not found"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)
    except BrokenPipeError:
        # Downstream closed pipe (e.g., head -n 10)
        # Terminate tail process gracefully
        pass
    except KeyboardInterrupt:
        # User pressed Ctrl+C
        pass
    finally:
        # Clean up subprocess
        try:
            proc.terminate()
            proc.wait(timeout=1)
        except:
            proc.kill()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='JN tail shell plugin')
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
