"""Head command - output first N records."""

import json
import subprocess
import sys

import click

from ...addressing import (
    AddressResolutionError,
    AddressResolver,
    parse_address,
)
from ...context import pass_context
from ...core.streaming import head as stream_head
from ..helpers import check_uv_available


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
    """
    try:
        # Support "jn head N" by treating a numeric first arg as line count
        if source and source.isdigit():
            n = int(source)
            source = None

        if source:
            check_uv_available()

            # Parse address
            addr = parse_address(source)

            # Create resolver and resolve address
            resolver = AddressResolver(ctx.plugin_dir, ctx.cache_path)
            resolved = resolver.resolve(addr, mode="read")

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
                # Protocol or profile
                if resolved.headers:
                    cmd.extend(["--headers", json.dumps(resolved.headers)])
                cmd.append(resolved.url)
                stdin_source = subprocess.DEVNULL
                infile = None
            elif addr.type == "stdio":
                # Stdin
                stdin_source = sys.stdin
                infile = None
            else:
                # File
                infile = open(addr.base)
                stdin_source = infile

            # Execute plugin
            proc = subprocess.Popen(
                cmd,
                stdin=stdin_source,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Stream first n lines
            stream_head(proc.stdout, n, sys.stdout)
            proc.wait()

            # Close file if opened
            if infile:
                infile.close()

            # Check for errors
            if proc.returncode != 0:
                error_msg = proc.stderr.read()
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
