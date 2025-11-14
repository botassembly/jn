"""jc fallback for shell commands.

When no custom plugin matches a shell command, try using jc to parse it.
"""

import json
import shlex
import shutil
import subprocess
import sys
from typing import Any, Iterator, TextIO

from ..process_utils import popen_with_validation, run_with_validation

# jc commands that have streaming parsers (output NDJSON directly)
# Note: some commands (e.g., ls) may require certain flags for streaming
# to be valid. See logic in execute_with_jc for conditional handling.
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
    return shutil.which("jc") is not None


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
        result = run_with_validation(
            ["jc", "--help"], capture_output=True, text=True, timeout=2
        )
        # Look for --commandname in help output
        return f"--{command}" in result.stdout
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
            "hint": "https://github.com/kellyjonbrazil/jc",
        }
        print(json.dumps(error), file=sys.stderr, flush=True)
        return 1

    # Parse command safely
    try:
        args = shlex.split(command_str)
    except ValueError as e:
        error = {"_error": f"Invalid command syntax: {e}"}
        print(json.dumps(error), file=sys.stderr, flush=True)
        return 1

    if not args:
        error = {"_error": "Empty command"}
        print(json.dumps(error), file=sys.stderr, flush=True)
        return 1

    command = args[0]

    # Check if jc supports this command
    if not supports_command(command):
        error = {
            "_error": f"jc does not support command: {command}",
            "hint": "Run 'jc --help' to see supported commands",
        }
        print(json.dumps(error), file=sys.stderr, flush=True)
        return 1

    # Determine if streaming parser is appropriate
    # Special-case: jc's streaming ls parser requires '-l'.
    use_streaming = False
    if command == "ls":
        # Use streaming only when '-l' is present in any combined flag (e.g., -l, -la, -al)
        # Stop parsing flags after '--'
        for arg in args[1:]:
            if arg == "--":
                break
            if arg.startswith("-") and "l" in arg.lstrip("-"):
                use_streaming = True
                break
    else:
        use_streaming = command in STREAMING_PARSERS

    jc_parser = f"--{command}-s" if use_streaming else f"--{command}"
    jc_cmd = ["jc", jc_parser]

    try:
        # Chain: command | jc
        cmd_proc = popen_with_validation(
            args, stdout=subprocess.PIPE, stderr=sys.stderr
        )

        jc_proc = popen_with_validation(
            jc_cmd,
            stdin=cmd_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1,  # Line buffered
        )

        # CRITICAL: Close command stdout in parent to enable SIGPIPE
        if cmd_proc.stdout:
            cmd_proc.stdout.close()

        # Stream output
        if use_streaming:
            # Streaming parser outputs NDJSON directly
            assert jc_proc.stdout is not None

            for line in jc_proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
        else:
            # Batch parser outputs JSON array - convert to NDJSON
            assert jc_proc.stdout is not None

            try:
                for record in _iter_json_records(jc_proc.stdout):
                    print(json.dumps(record), flush=True)
            except json.JSONDecodeError as e:
                error = {"_error": f"Failed to parse jc output: {e}"}
                print(json.dumps(error), file=sys.stderr, flush=True)
                return 1

        if jc_proc.stdout and not jc_proc.stdout.closed:
            jc_proc.stdout.close()

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
        print(json.dumps(error), file=sys.stderr, flush=True)
        return 1
    except BrokenPipeError:
        # Downstream closed pipe (e.g., head -n 10) - normal
        return 0
    except KeyboardInterrupt:
        # User interrupted - normal
        return 0


def _iter_json_records(stream: TextIO) -> Iterator[Any]:
    """Stream JSON records from either an array or single JSON object."""

    decoder = json.JSONDecoder()
    buffer = ""
    need_data = True
    in_array: bool | None = None
    eof = False

    while True:
        if (need_data or not buffer) and not eof:
            chunk = stream.read(8192)
            if chunk:
                buffer += chunk
                need_data = False
            else:
                eof = True

        stripped = buffer.lstrip()
        buffer = stripped

        if not buffer:
            if eof:
                if in_array:
                    raise json.JSONDecodeError(
                        "Unexpected end of JSON array", buffer or "", 0
                    )
                return
            need_data = True
            continue

        if in_array is None:
            if buffer[0] == "[":
                in_array = True
                buffer = buffer[1:]
                need_data = not buffer
                continue

            decoded = _try_decode(decoder, buffer)
            if decoded is None:
                if eof:
                    raise json.JSONDecodeError(
                        "Invalid JSON output", buffer, 0
                    )
                need_data = True
                continue

            value, idx = decoded
            yield value
            buffer = buffer[idx:]
            buffer = buffer.lstrip()
            if buffer:
                raise json.JSONDecodeError(
                    "Unexpected trailing data", buffer, 0
                )
            return

        if buffer[0] == "]":
            return

        decoded = _try_decode(decoder, buffer)
        if decoded is None:
            if eof:
                raise json.JSONDecodeError(
                    "Invalid JSON array output", buffer, 0
                )
            need_data = True
            continue

        value, idx = decoded
        yield value
        buffer = buffer[idx:]
        buffer = buffer.lstrip()

        if buffer.startswith(","):
            buffer = buffer[1:]
        elif buffer.startswith("]"):
            return

        need_data = not buffer


def _try_decode(
    decoder: json.JSONDecoder, buffer: str
) -> tuple[Any, int] | None:  # pragma: no cover - helper
    try:
        return decoder.raw_decode(buffer)
    except json.JSONDecodeError:
        return None
