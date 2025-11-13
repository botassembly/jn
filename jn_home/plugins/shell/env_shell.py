#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["jc>=1.23.0"]
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
import shutil
import shlex


def reads(command_str=None):
    """Execute env command and stream NDJSON records.

    Args:
        command_str: Full command string like "env" (rarely needs args)
    """
    if not command_str:
        command_str = "env"

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

    if not args or args[0] != 'env':
        error = {"_error": f"Expected env command, got: {command_str}"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    # Build jc command
    jc_cmd = ['jc', '--env']

    try:
        # Chain: env [args] | jc
        env_proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=sys.stderr
        )

        jc_proc = subprocess.Popen(
            jc_cmd,
            stdin=env_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True
        )

        # CRITICAL: Close env stdout in parent to enable SIGPIPE propagation
        env_proc.stdout.close()

        # Read jc output (JSON array)
        output = jc_proc.stdout.read()

        # Wait for both processes
        jc_exit = jc_proc.wait()
        env_exit = env_proc.wait()

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
        if env_exit != 0:
            sys.exit(env_exit)

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
