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
from ..helpers import check_uv_available


def _build_command(stage: ExecutionStage) -> list:
    """Build command from execution stage."""
    cmd = ["uv", "run", "--script", stage.plugin_path, "--mode", stage.mode]

    # Add configuration parameters
    for key, value in stage.config.items():
        cmd.extend([f"--{key}", str(value)])

    # Add URL if present
    if stage.url:
        if stage.headers:
            cmd.extend(["--headers", json.dumps(stage.headers)])
        cmd.append(stage.url)

    return cmd


def _execute_single_stage_read(stage: ExecutionStage, addr: Address) -> None:
    """Execute single-stage read pipeline."""
    cmd = _build_command(stage)

    # Determine input source
    if stage.url:
        # Protocol or profile - URL passed as argument
        stdin_source = subprocess.DEVNULL
        infile = None
    elif addr.type == "stdio":
        # Stdin
        stdin_source = sys.stdin
        infile = None
    else:
        # File - open and pass as stdin
        infile = open(addr.base, "r")
        stdin_source = infile

    # Execute plugin
    proc = subprocess.Popen(
        cmd,
        stdin=stdin_source,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
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
    )

    # Start format plugin (parses bytes to NDJSON)
    # Keep in binary mode since stdin needs to receive binary data
    format_proc = subprocess.Popen(
        format_cmd,
        stdin=protocol_proc.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,  # Binary mode for stdin (receives raw bytes)
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
    """
    try:
        check_uv_available()

        # Parse address
        addr = parse_address(input_file)

        # Plan execution (may be 1 or 2 stages)
        resolver = AddressResolver(ctx.plugin_dir, ctx.cache_path)
        stages = resolver.plan_execution(addr, mode="read")

        if len(stages) == 2:
            # Two-stage pipeline: protocol (raw) → format (read)
            _execute_two_stage_read(stages[0], stages[1])
        else:
            # Single-stage execution
            _execute_single_stage_read(stages[0], addr)

    except ValueError as e:
        click.echo(f"Error: Invalid address syntax: {e}", err=True)
        sys.exit(1)
    except AddressResolutionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
