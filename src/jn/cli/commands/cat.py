"""Cat command - read files and output NDJSON."""

import json
import subprocess
import sys
from contextlib import ExitStack
from urllib.parse import urlencode

import click

from ...addressing import (
    AddressResolutionError,
    AddressResolver,
    ExecutionStage,
    parse_address,
)
from ...context import pass_context
from ...filtering import build_jq_filter, separate_config_and_filters
from ...introspection import get_plugin_config_params
from ...process_utils import popen_with_validation
from ...shell.jc_fallback import execute_with_jc, supports_command
from ..helpers import build_subprocess_env_for_coverage, check_uv_available


def _build_command(
    stage: ExecutionStage, command_str: str | None = None
) -> list[str]:
    """Build command from execution stage.

    Args:
        stage: Execution stage with plugin info
        command_str: Optional command string for shell plugins (overrides stage.url)
    """
    cmd = [
        "uv",
        "run",
        "--quiet",
        "--script",
        stage.plugin_path,
        "--mode",
        stage.mode,
    ]

    # DEBUG
    sys.stderr.flush()

    # Add configuration parameters
    for key, value in stage.config.items():
        # Convert underscores to dashes for CLI arguments (e.g., file_limit -> file-limit)
        cli_key = key.replace("_", "-")
        if isinstance(value, bool):
            if value:
                # True: pass --flag (works for action="store_true")
                cmd.append(f"--{cli_key}")
            else:
                # False: pass --flag false (for regular bool params like --header)
                cmd.extend([f"--{cli_key}", "false"])
        else:
            cmd.extend([f"--{cli_key}", str(value)])

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


def _execute_with_filter(stages, addr, filters, home_dir=None):
    """Execute pipeline with optional filter stage.

    Args:
        stages: Execution stages to run
        addr: Parsed address
        filters: Optional jq filters to apply
        home_dir: JN home directory (overrides $JN_HOME)
    """

    with ExitStack() as stack:
        if len(stages) >= 2:
            # Multi-stage pipeline (2 or 3 stages)
            procs = []
            prev_proc = None

            for i, stage in enumerate(stages):
                cmd = _build_command(stage)
                is_last = i == len(stages) - 1
                is_first = i == 0

                # Determine stdin source
                if is_first:
                    if stage.url or addr.type == "profile":
                        stdin_source = subprocess.DEVNULL
                    elif addr.type == "file":
                        file_path = addr.base
                        if addr.compression:
                            file_path = f"{file_path}.{addr.compression}"
                        stdin_source = stack.enter_context(
                            open(file_path, "rb")
                        )
                    elif addr.type == "stdio":
                        stdin_source = sys.stdin.buffer
                    else:
                        stdin_source = subprocess.DEVNULL
                else:
                    stdin_source = prev_proc.stdout

                text_mode = is_last and stage.mode == "read"
                proc = popen_with_validation(
                    cmd,
                    stdin=stdin_source,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=text_mode,
                    env=build_subprocess_env_for_coverage(home_dir=home_dir),
                )

                if prev_proc:
                    prev_proc.stdout.close()

                procs.append(proc)
                prev_proc = proc

            reader_proc = procs[-1]
            reader_stdout = reader_proc.stdout
            reader_stderr = reader_proc.stderr
            other_proc = procs[0] if len(procs) > 1 else None
            all_procs = procs
        elif len(stages) == 1:
            stage = stages[0]
            is_shell_plugin = "/shell/" in stage.plugin_path
            is_glob_plugin = addr.type == "glob"

            # Shell plugins and glob plugins receive addr.base as command/pattern argument
            cmd = (
                _build_command(stage, command_str=addr.base)
                if (is_shell_plugin or is_glob_plugin)
                else _build_command(stage)
            )

            if is_shell_plugin or is_glob_plugin or stage.url or addr.type == "profile":
                stdin_source = subprocess.DEVNULL
            elif addr.type == "stdio":
                stdin_source = sys.stdin
            else:
                stdin_source = stack.enter_context(open(addr.base))

            reader_proc = popen_with_validation(
                cmd,
                stdin=stdin_source,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=build_subprocess_env_for_coverage(home_dir=home_dir),
            )

            reader_stdout = reader_proc.stdout
            reader_stderr = reader_proc.stderr
            other_proc = None
            all_procs = None
        else:
            for line in sys.stdin:
                sys.stdout.write(line)
            return

        if filters:
            jq_expr = build_jq_filter(filters)
            filter_proc = popen_with_validation(
                [sys.executable, "-m", "jn.cli.main", "filter", jq_expr],
                stdin=reader_stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=build_subprocess_env_for_coverage(home_dir=home_dir),
            )
            reader_stdout.close()
            output_stdout = filter_proc.stdout
            final_proc = filter_proc
        else:
            output_stdout = reader_stdout
            final_proc = reader_proc

        for line in output_stdout:
            sys.stdout.write(line)

        final_proc.wait()
        reader_proc.wait()

        if all_procs:
            for proc in all_procs:
                if proc != reader_proc:
                    proc.wait()
        elif other_proc:
            other_proc.wait()

        if final_proc.returncode != 0:
            error_msg = final_proc.stderr.read() if filters else ""
            if error_msg:
                click.echo(f"Error: Filter error: {error_msg}", err=True)
            sys.exit(1)

        if reader_proc.returncode != 0:
            error_msg = reader_stderr.read()
            click.echo(f"Error: Reader error: {error_msg}", err=True)
            sys.exit(1)

        if all_procs:
            for i, proc in enumerate(all_procs):
                if proc != reader_proc and proc.returncode != 0:
                    error_msg = proc.stderr.read()
                    if isinstance(error_msg, bytes):
                        error_msg = error_msg.decode("utf-8")
                    stage_name = (
                        "Stage"
                        if i == 0
                        else (
                            "Decompression"
                            if i == 1 and len(all_procs) == 3
                            else "Protocol"
                        )
                    )
                    click.echo(
                        f"Error: {stage_name} error: {error_msg}", err=True
                    )
                    sys.exit(1)
        elif other_proc and other_proc.returncode != 0:
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
            resolver = AddressResolver(
                ctx.plugin_dir, ctx.cache_path, ctx.home
            )

            try:
                stages = resolver.plan_execution(addr, mode="read")
            except AddressResolutionError:
                command_name = (
                    input_file.split()[0] if " " in input_file else input_file
                )
                if supports_command(command_name):
                    exit_code = execute_with_jc(input_file)
                    sys.exit(exit_code)
                else:
                    raise

            _execute_with_filter(stages, addr, filters=[], home_dir=ctx.home)
            return

        # Parameters exist - separate config from filters
        resolver = AddressResolver(ctx.plugin_dir, ctx.cache_path, ctx.home)

        try:
            stages = resolver.plan_execution(addr, mode="read")
        except AddressResolutionError:
            command_name = (
                input_file.split()[0] if " " in input_file else input_file
            )
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

        # For protocol plugins handling profiles or globs, skip config/filter separation
        # These plugins manage their own parameter handling internally
        if addr.type in ("profile", "glob") and final_stage.plugin_path:
            # Check plugin metadata to see if it manages its own parameters
            from ...plugins.service import get_cached_plugins_with_fallback

            plugins = get_cached_plugins_with_fallback(
                ctx.plugin_dir,
                ctx.cache_path,
            )

            # Find plugin metadata by path
            plugin_meta = None
            for meta in plugins.values():
                if final_stage.plugin_path == meta.path:
                    plugin_meta = meta
                    break

            if plugin_meta and plugin_meta.manages_parameters:
                # Plugin handles own parameter parsing - skip config/filter separation
                _execute_with_filter(
                    stages, addr, filters=[], home_dir=ctx.home
                )
                return

        # Introspect plugin to get config params
        config_params = get_plugin_config_params(final_stage.plugin_path)

        # Separate config from filters
        config, filters = separate_config_and_filters(
            addr.parameters, config_params
        )

        # Rebuild address with ONLY config parameters (removing filters)
        # Reconstruct address with only config
        base_addr = addr.base
        # Add compression extension back if present
        if addr.compression:
            base_addr = f"{base_addr}.{addr.compression}"
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
        _execute_with_filter(stages, addr, filters, home_dir=ctx.home)

    except ValueError as e:
        click.echo(f"Error: Invalid address syntax: {e}", err=True)
        sys.exit(1)
    except AddressResolutionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
