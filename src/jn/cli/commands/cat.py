"""Cat command - read files and output NDJSON."""

import json
import subprocess
import sys

import click

from ...addressing import (
    Address,
    AddressResolutionError,
    AddressResolver,
    ExecutionStage,
    parse_address,
)
from ...context import pass_context
from ...shell.jc_fallback import execute_with_jc, supports_command
from ..helpers import build_subprocess_env_for_coverage, check_uv_available


def _build_command(stage: ExecutionStage, command_str: str = None) -> list:
    """Build command from execution stage.

    Args:
        stage: Execution stage with plugin info
        command_str: Optional command string for shell plugins (overrides stage.url)
    """
    cmd = ["uv", "run", "--script", stage.plugin_path, "--mode", stage.mode]

    # Add configuration parameters
    for key, value in stage.config.items():
        cmd.extend([f"--{key}", str(value)])

    # Add URL or command string if present
    if command_str:
        # Shell command or explicit override
        cmd.append(command_str)
    elif stage.url:
        # Protocol/profile URL
        if stage.headers:
            cmd.extend(["--headers", json.dumps(stage.headers)])
        cmd.append(stage.url)

    return cmd


def _execute_single_stage_read(stage: ExecutionStage, addr: Address) -> None:
    """Execute single-stage read pipeline."""
    # Check if this is a shell command plugin
    is_shell_plugin = "/shell/" in stage.plugin_path

    # Build command - for shell plugins, pass the command string
    if is_shell_plugin:
        cmd = _build_command(stage, command_str=addr.base)
    else:
        cmd = _build_command(stage)

    # Determine input source
    if is_shell_plugin or stage.url:
        # Shell command or protocol - command/URL passed as argument
        stdin_source = subprocess.DEVNULL
        infile = None
    elif addr.type == "stdio":
        # Stdin
        stdin_source = sys.stdin
        infile = None
    else:
        # File - open and pass as stdin
        infile = open(addr.base)
        stdin_source = infile

    # Execute plugin
    proc = subprocess.Popen(
        cmd,
        stdin=stdin_source,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=build_subprocess_env_for_coverage(),
    )

    # Stream output
    for line in proc.stdout:
        sys.stdout.write(line)

    proc.wait()

    # Close file if opened
    if infile:
        infile.close()

    # Check for errors
    if proc.returncode != 0:
        error_msg = proc.stderr.read()
        click.echo(f"Error: Reader error: {error_msg}", err=True)
        sys.exit(1)


def _execute_two_stage_read(
    protocol_stage: ExecutionStage, format_stage: ExecutionStage
) -> None:
    """Execute two-stage read pipeline: protocol (raw) → format (read)."""
    # Build commands
    protocol_cmd = _build_command(protocol_stage)
    format_cmd = _build_command(format_stage)

    # Start protocol plugin (fetches raw bytes)
    protocol_proc = subprocess.Popen(
        protocol_cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,  # Binary mode for raw bytes
        env=build_subprocess_env_for_coverage(),
    )

    # Start format plugin (parses bytes to NDJSON)
    # Keep in binary mode since stdin needs to receive binary data
    format_proc = subprocess.Popen(
        format_cmd,
        stdin=protocol_proc.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,  # Binary mode for stdin (receives raw bytes)
        env=build_subprocess_env_for_coverage(),
    )

    # Close protocol stdout in parent (critical for SIGPIPE)
    protocol_proc.stdout.close()

    # Stream output (decode text from binary stdout)
    for line in format_proc.stdout:
        sys.stdout.write(line.decode("utf-8"))

    # Wait for both processes
    format_proc.wait()
    protocol_proc.wait()

    # Check for errors (decode binary stderr)
    if format_proc.returncode != 0:
        error_msg = format_proc.stderr.read().decode("utf-8")
        click.echo(f"Error: Format reader error: {error_msg}", err=True)
        sys.exit(1)

    if protocol_proc.returncode != 0:
        error_msg = protocol_proc.stderr.read().decode("utf-8")
        click.echo(f"Error: Protocol reader error: {error_msg}", err=True)
        sys.exit(1)


@click.command()
@click.argument("input_file")
@pass_context
def cat(ctx, input_file):
    """Read file and output NDJSON to stdout.

    Supports universal addressing syntax: address[~format][?parameters]

    Examples:
        # Basic files
        jn cat data.csv                        # Auto-detect format
        jn cat data.txt~csv                    # Force CSV format
        jn cat data.csv~csv?delimiter=;        # CSV with semicolon delimiter

        # Stdin
        cat data.csv | jn cat "-~csv"          # Read stdin as CSV
        cat data.tsv | jn cat "-~csv?delimiter=%09"  # Tab-delimited (%09 = tab)

        # Profiles with query strings
        jn cat "@api/source?gene=BRAF&limit=100"
        jn cat "@gmail/inbox?from=boss&is=unread"

        # Protocol URLs
        jn cat "http://example.com/data.json"
        jn cat "s3://bucket/data.csv"

    Note:
        When passing addresses that start with '-', use '--' to stop
        option parsing before the argument, e.g.:
          jn cat -- "-~csv"
    """
    try:
        check_uv_available()

        # Parse address
        addr = parse_address(input_file)

        # Plan execution (may be 1 or 2 stages)
        resolver = AddressResolver(ctx.plugin_dir, ctx.cache_path)

        try:
            stages = resolver.plan_execution(addr, mode="read")
        except AddressResolutionError:
            # No plugin found - try jc fallback for shell commands
            command_name = input_file.split()[0] if ' ' in input_file else input_file
            if supports_command(command_name):
                exit_code = execute_with_jc(input_file)
                sys.exit(exit_code)
            else:
                # Re-raise if jc doesn't support it either
                raise

        if len(stages) == 2:
            # Two-stage pipeline: protocol (raw) → format (read)
            _execute_two_stage_read(stages[0], stages[1])
        elif len(stages) == 1:
            # Single-stage execution
            _execute_single_stage_read(stages[0], addr)
        else:
            # Pass-through NDJSON from stdin when no plugin stage is needed
            for line in sys.stdin:
                sys.stdout.write(line)

    except ValueError as e:
        click.echo(f"Error: Invalid address syntax: {e}", err=True)
        sys.exit(1)
    except AddressResolutionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
