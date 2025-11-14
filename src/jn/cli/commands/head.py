"""Head command - output first N records."""

import json
import subprocess
import sys
from contextlib import ExitStack

import click

from ...addressing import (
    AddressResolutionError,
    AddressResolver,
    parse_address,
)
from ...context import pass_context
from ...core.streaming import head as stream_head
from ...filtering import build_jq_filter, separate_config_and_filters
from ...introspection import get_plugin_config_params
from ...process_utils import popen_with_validation
from ..helpers import build_subprocess_env_for_coverage, check_uv_available


@click.command()
@click.argument("source", required=False)
@click.option(
    "-n",
    "--lines",
    "n",
    type=int,
    default=10,
    help="Number of lines to output",
)
@pass_context
def head(ctx, source, n):
    """Output first N records from NDJSON stream.

    Supports universal addressing syntax: address[~format][?parameters]

    Examples:
        # From piped input
        jn cat data.csv | jn head         # First 10 records
        jn cat data.csv | jn head -n 5    # First 5 records

        # Directly from file
        jn head data.csv -n 5             # Auto-detect format
        jn head data.txt~csv -n 10        # Force CSV format
        jn head "data.csv~csv?delimiter=;" -n 5  # With parameters

    Note:
        When passing addresses that start with '-', use '--' to stop
        option parsing before the argument.
    """
    try:
        # Support "jn head N" by treating a numeric first arg as line count
        if source and source.isdigit():
            n = int(source)
            source = None

        if n < 0:
            click.echo("Error: --lines must be >= 0", err=True)
            sys.exit(1)

        if source:
            check_uv_available()

            # Parse address
            addr = parse_address(source)

            # Create resolver and do initial resolution to get plugin path
            resolver = AddressResolver(ctx.plugin_dir, ctx.cache_path)
            resolved = resolver.resolve(addr, mode="read")

            # Separate config parameters from filters if parameters exist
            filters = []
            if addr.parameters:
                # Get config params from plugin
                config_params = get_plugin_config_params(resolved.plugin_path)
                config, filters = separate_config_and_filters(
                    addr.parameters, config_params
                )

                # Rebuild address with only config parameters if filters exist
                if filters:
                    from urllib.parse import urlencode

                    base_uri = addr.base
                    if addr.format_override:
                        base_uri = f"{base_uri}~{addr.format_override}"

                    if config:
                        query_str = urlencode(config)
                        full_uri = f"{base_uri}?{query_str}"
                    else:
                        full_uri = base_uri

                    # Re-parse and re-resolve the cleaned address
                    addr = parse_address(full_uri)
                    resolved = resolver.resolve(addr, mode="read")

            with ExitStack() as stack:
                # Build command
                cmd = [
                    "uv",
                    "run",
                    "--script",
                    resolved.plugin_path,
                    "--mode",
                    "read",
                ]

                # Add configuration parameters
                for key, value in resolved.config.items():
                    cmd.extend([f"--{key}", str(value)])

                # Determine input source
                if resolved.url:
                    if resolved.headers:
                        cmd.extend(["--headers", json.dumps(resolved.headers)])
                    cmd.append(resolved.url)
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
                    env=build_subprocess_env_for_coverage(),
                )

                if filters:
                    jq_expr = build_jq_filter(filters)
                    filter_proc = popen_with_validation(
                        [
                            sys.executable,
                            "-m",
                            "jn.cli.main",
                            "filter",
                            jq_expr,
                        ],
                        stdin=reader_proc.stdout,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        env=build_subprocess_env_for_coverage(),
                    )
                    reader_proc.stdout.close()
                    output_stream = filter_proc.stdout
                else:
                    filter_proc = None
                    output_stream = reader_proc.stdout

                stream_head(output_stream, n, sys.stdout)

                if filter_proc:
                    filter_proc.wait()
                reader_proc.wait()

            # Check for errors
            if filter_proc and filter_proc.returncode != 0:
                error_msg = filter_proc.stderr.read()
                click.echo(f"Error: Filter failed: {error_msg}", err=True)
                sys.exit(1)

            if reader_proc.returncode != 0:
                error_msg = reader_proc.stderr.read()
                click.echo(f"Error: {error_msg}", err=True)
                sys.exit(1)
        else:
            # Read from stdin
            stream_head(sys.stdin, n, sys.stdout)

    except ValueError as e:
        click.echo(f"Error: Invalid address syntax: {e}", err=True)
        sys.exit(1)
    except AddressResolutionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
