#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = ["^tail($| )", "^tail .*"]
# ///

"""
JN Shell Plugin: tail

Execute `tail` command to stream file contents.

Usage:
    jn cat "tail /var/log/syslog"
    jn cat "tail -f /var/log/app.log"
    jn cat "tail -n 50 /var/log/app.log"
    jn sh tail -f /var/log/app.log
    jn sh tail -n 100 /var/log/app.log | jn filter '.line | contains("ERROR")'

The command can be any valid tail invocation.

Output schema:
    {
        "line": string,         # The log line
        "line_number": integer  # Sequential line number (1-based)
    }

Follow mode notes:
    - Runs indefinitely until interrupted (Ctrl+C) or pipe closed
    - Uses `tail -f` or `tail -F` which handles log rotation
    - Backpressure automatic: if downstream slow, tail blocks
    - Memory constant regardless of file size or growth rate
"""

import subprocess
import sys
import json
import shlex

from typing import Optional


def reads(command_str=None):
    """Execute tail command and stream NDJSON records.

    Args:
        command_str: Full command string like "tail -f /var/log/syslog" or "tail file.log"
    """
    if not command_str:
        error = {"_error": "tail requires a file argument"}
        print(json.dumps(error), file=sys.stderr, flush=True)
        sys.exit(1)

    # Parse command string into args
    try:
        args = shlex.split(command_str)
    except ValueError as e:
        error = {"_error": f"Invalid command syntax: {e}"}
        print(json.dumps(error), file=sys.stderr, flush=True)
        sys.exit(1)

    if not args or args[0] != 'tail':
        error = {"_error": f"Expected tail command, got: {command_str}"}
        print(json.dumps(error), file=sys.stderr, flush=True)
        sys.exit(1)

    proc: Optional[subprocess.Popen[str]] = None

    try:
        # Spawn tail process
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1  # Line buffered
        )

        # Stream output line-by-line
        line_number = 0
        assert proc.stdout is not None

        for line in proc.stdout:
            line_number += 1
            record = {
                "line": line.rstrip(),
                "line_number": line_number
            }
            print(json.dumps(record), flush=True)

        proc.stdout.close()
        proc.wait()

    except FileNotFoundError as e:
        error = {"_error": f"Command not found: {e}"}
        print(json.dumps(error), file=sys.stderr, flush=True)
        sys.exit(1)
    except BrokenPipeError:
        # Downstream closed pipe (e.g., head -n 10)
        pass
    except KeyboardInterrupt:
        # User pressed Ctrl+C
        pass
    finally:
        # Clean up subprocess
        if proc is not None:
            if proc.stdout and not proc.stdout.closed:
                proc.stdout.close()
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                    proc.wait(timeout=1)
                except OSError:
                    pass
            except (ProcessLookupError, OSError):
                pass


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='JN tail shell plugin')
    parser.add_argument('--mode', default='read', help='Plugin mode (read/write)')
    parser.add_argument('address', nargs='?', help='Command string (e.g., "tail -f /var/log/app.log")')

    args = parser.parse_args()

    if args.mode == 'read':
        reads(args.address)
    else:
        error = {"_error": f"Unsupported mode: {args.mode}. Only 'read' supported."}
        print(json.dumps(error), file=sys.stderr, flush=True)
        sys.exit(1)
