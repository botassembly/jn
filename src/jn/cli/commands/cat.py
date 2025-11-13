"""Cat command - read files and output NDJSON."""

import json
import subprocess
import sys
from urllib.parse import urlencode

import click

from ...addressing import (
    Address,
    AddressResolutionError,
    AddressResolver,
    ExecutionStage,
    parse_address,
)
from ...context import pass_context
from ...filtering import build_jq_filter, separate_config_and_filters
from ...introspection import get_plugin_config_params
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


def _execute_with_filter(stages, addr, filters):
    """Execute pipeline with optional filter stage.

    Args:
        stages: List of execution stages (1 or 2)
        addr: Parsed address
        filters: List of filter tuples, or empty list
    """
    # Build reader processes
    if len(stages) == 2:
        # Two-stage: protocol + format
        protocol_cmd = _build_command(stages[0])
        format_cmd = _build_command(stages[1])

        protocol_proc = subprocess.Popen(
            protocol_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            env=build_subprocess_env_for_coverage(),
        )

        format_proc = subprocess.Popen(
            format_cmd,
            stdin=protocol_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=build_subprocess_env_for_coverage(),
        )

        protocol_proc.stdout.close()
        reader_stdout = format_proc.stdout
        reader_stderr = format_proc.stderr
        reader_proc = format_proc
        other_proc = protocol_proc

    elif len(stages) == 1:
        # Single-stage
        stage = stages[0]
        is_shell_plugin = "/shell/" in stage.plugin_path

        if is_shell_plugin:
            cmd = _build_command(stage, command_str=addr.base)
        else:
            cmd = _build_command(stage)

        # Determine input source
        if is_shell_plugin or stage.url:
            stdin_source = subprocess.DEVNULL
            infile = None
        elif addr.type == "stdio":
            stdin_source = sys.stdin
            infile = None
        else:
            infile = open(addr.base)
            stdin_source = infile

        reader_proc = subprocess.Popen(
            cmd,
            stdin=stdin_source,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=build_subprocess_env_for_coverage(),
        )

        reader_stdout = reader_proc.stdout
        reader_stderr = reader_proc.stderr
        other_proc = None
        infile_handle = infile if 'infile' in locals() else None
    else:
        # Pass-through (no stages)
        for line in sys.stdin:
            sys.stdout.write(line)
        return

    # Add filter stage if filters exist
    if filters:
        jq_expr = build_jq_filter(filters)

        filter_proc = subprocess.Popen(
            ["jn", "filter", jq_expr],
            stdin=reader_stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=build_subprocess_env_for_coverage(),
        )

        reader_stdout.close()  # Close reader stdout in parent
        output_stdout = filter_proc.stdout
        final_proc = filter_proc
    else:
        output_stdout = reader_stdout
        final_proc = reader_proc

    # Stream output
    for line in output_stdout:
        sys.stdout.write(line)

    # Wait for all processes
    final_proc.wait()
    reader_proc.wait()
    if other_proc:
        other_proc.wait()

    # Close file if opened
    if len(stages) == 1 and 'infile_handle' in locals() and infile_handle:
        infile_handle.close()

    # Check for errors
    if final_proc.returncode != 0:
        error_msg = final_proc.stderr.read() if filters else ""
        if error_msg:
            click.echo(f"Error: Filter error: {error_msg}", err=True)
        sys.exit(1)

    if reader_proc.returncode != 0:
        error_msg = reader_stderr.read()
        click.echo(f"Error: Reader error: {error_msg}", err=True)
        sys.exit(1)

    if other_proc and other_proc.returncode != 0:
        error_msg = other_proc.stderr.read()
        if isinstance(error_msg, bytes):
            error_msg = error_msg.decode("utf-8")
        click.echo(f"Error: Protocol error: {error_msg}", err=True)
        sys.exit(1)


@click.command()
@click.argument("input_file")
@pass_context
def cat(ctx, input_file):
    """Read file and output NDJSON to stdout.

    Supports universal addressing syntax: address[~format][?parameters]

    Query parameters can be either config or filters:
    - Config params (delimiter, limit, etc.) are passed to the plugin
    - Filter params (field=value) are applied as jq filters after reading

    Filter syntax:
    - Same field multiple times: OR logic (city=NYC&city=LA)
    - Different fields: AND logic (city=NYC&age>25)

    Examples:
        # Basic files
        jn cat data.csv                        # Auto-detect format
        jn cat data.txt~csv                    # Force CSV format
        jn cat data.csv~csv?delimiter=;        # CSV with semicolon delimiter

        # Filtering
        jn cat 'data.csv?city=NYC'             # Filter: city equals NYC
        jn cat 'data.csv?city=NYC&city=LA'     # Filter: city equals NYC OR LA
        jn cat 'data.csv?city=NYC&age>25'      # Filter: city=NYC AND age>25
        jn cat 'data.csv?limit=100&city=NYC'   # Config (limit) + filter (city)

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

        # If no parameters, use original fast path
        if not addr.parameters:
            resolver = AddressResolver(ctx.plugin_dir, ctx.cache_path)

            try:
                stages = resolver.plan_execution(addr, mode="read")
            except AddressResolutionError:
                command_name = input_file.split()[0] if ' ' in input_file else input_file
                if supports_command(command_name):
                    exit_code = execute_with_jc(input_file)
                    sys.exit(exit_code)
                else:
                    raise

            _execute_with_filter(stages, addr, filters=[])
            return

        # Parameters exist - separate config from filters
        resolver = AddressResolver(ctx.plugin_dir, ctx.cache_path)

        try:
            stages = resolver.plan_execution(addr, mode="read")
        except AddressResolutionError:
            command_name = input_file.split()[0] if ' ' in input_file else input_file
            if supports_command(command_name):
                exit_code = execute_with_jc(input_file)
                sys.exit(exit_code)
            else:
                raise

        # Get the final stage (the one that will read data)
        if not stages:
            # No stages - pass through stdin
            for line in sys.stdin:
                sys.stdout.write(line)
            return

        final_stage = stages[-1]

        # Introspect plugin to get config params
        config_params = get_plugin_config_params(final_stage.plugin_path)

        # Separate config from filters
        config, filters = separate_config_and_filters(addr.parameters, config_params)

        # Rebuild address with ONLY config parameters (removing filters)
        # Reconstruct address with only config
        base_addr = addr.base
        if addr.format_override:
            base_addr = f"{base_addr}~{addr.format_override}"

        if config:
            # Build new address with config params
            query_str = urlencode(config)
            new_input = f"{base_addr}?{query_str}"
        else:
            # No config - just base address
            new_input = base_addr

        # Re-parse and re-plan with config-only address
        addr = parse_address(new_input)
        stages = resolver.plan_execution(addr, mode="read")

        # Execute with filter stage if needed
        _execute_with_filter(stages, addr, filters)

    except ValueError as e:
        click.echo(f"Error: Invalid address syntax: {e}", err=True)
        sys.exit(1)
    except AddressResolutionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
