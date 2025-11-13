"""jc fallback for shell commands.

When no custom plugin matches a shell command, try using jc to parse it.
"""

import json
import shlex
import shutil
import subprocess
import sys
from typing import Optional


# jc commands that have streaming parsers (output NDJSON directly)
STREAMING_PARSERS = {
    "ls",
    "ping",
    "traceroute",
    "dig",
    "git-log",
    "vmstat",
    "iostat",
    "mpstat",
    "netstat",
    "systemctl-ls",
}


def is_jc_available() -> bool:
    """Check if jc command is installed."""
    return shutil.which('jc') is not None


def supports_command(command: str) -> bool:
    """Check if jc supports a given command.

    Args:
        command: Command name (e.g., "ls", "ps", "df")

    Returns:
        True if jc has a parser for this command
    """
    if not is_jc_available():
        return False

    try:
        # jc --help lists all supported commands
        result = subprocess.run(
            ['jc', '--help'],
            capture_output=True,
            text=True,
            timeout=2
        )
        # Look for --commandname in help output
        return f'--{command}' in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def execute_with_jc(command_str: str) -> int:
    """Execute a shell command using jc to parse output to NDJSON.

    Streams NDJSON records to stdout. Acts as fallback when no custom
    plugin matches the command.

    Args:
        command_str: Full command string (e.g., "ls -l /tmp")

    Returns:
        Exit code (0 on success)
    """
    if not is_jc_available():
        error = {
            "_error": "jc not found. Install: pip install jc",
            "hint": "https://github.com/kellyjonbrazil/jc"
        }
        print(json.dumps(error), file=sys.stderr)
        return 1

    # Parse command safely
    try:
        args = shlex.split(command_str)
    except ValueError as e:
        error = {"_error": f"Invalid command syntax: {e}"}
        print(json.dumps(error), file=sys.stderr)
        return 1

    if not args:
        error = {"_error": "Empty command"}
        print(json.dumps(error), file=sys.stderr)
        return 1

    command = args[0]

    # Check if jc supports this command
    if not supports_command(command):
        error = {
            "_error": f"jc does not support command: {command}",
            "hint": "Run 'jc --help' to see supported commands"
        }
        print(json.dumps(error), file=sys.stderr)
        return 1

    # Determine if streaming parser available
    use_streaming = command in STREAMING_PARSERS
    jc_parser = f'--{command}-s' if use_streaming else f'--{command}'
    jc_cmd = ['jc', jc_parser]

    try:
        # Chain: command | jc
        cmd_proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=sys.stderr
        )

        jc_proc = subprocess.Popen(
            jc_cmd,
            stdin=cmd_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1  # Line buffered
        )

        # CRITICAL: Close command stdout in parent to enable SIGPIPE
        if cmd_proc.stdout:
            cmd_proc.stdout.close()

        # Stream output
        if use_streaming:
            # Streaming parser outputs NDJSON directly
            for line in jc_proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
        else:
            # Batch parser outputs JSON array - convert to NDJSON
            output = jc_proc.stdout.read()
            try:
                records = json.loads(output) if output.strip() else []

                # Handle both arrays and single objects
                if isinstance(records, list):
                    for record in records:
                        print(json.dumps(record))
                else:
                    print(json.dumps(records))

            except json.JSONDecodeError as e:
                error = {"_error": f"Failed to parse jc output: {e}"}
                print(json.dumps(error), file=sys.stderr)
                return 1

        # Wait for both processes
        jc_exit = jc_proc.wait()
        cmd_exit = cmd_proc.wait()

        # Exit with error if either command failed
        if jc_exit != 0:
            return jc_exit
        if cmd_exit != 0:
            return cmd_exit

        return 0

    except FileNotFoundError as e:
        error = {"_error": f"Command not found: {e}"}
        print(json.dumps(error), file=sys.stderr)
        return 1
    except BrokenPipeError:
        # Downstream closed pipe (e.g., head -n 10) - normal
        return 0
    except KeyboardInterrupt:
        # User interrupted - normal
        return 0
