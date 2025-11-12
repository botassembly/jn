"""Cat command - read files and output NDJSON."""

import json
import subprocess
import sys

import click

from ...addressing import AddressResolutionError, AddressResolver, parse_address
from ...context import pass_context
from ..helpers import check_uv_available


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

        # Create resolver and resolve address
        resolver = AddressResolver(ctx.plugin_dir, ctx.cache_path)
        resolved = resolver.resolve(addr, mode="read")

        # Build command
        cmd = ["uv", "run", "--script", resolved.plugin_path, "--mode", "read"]

        # Add configuration parameters
        for key, value in resolved.config.items():
            cmd.extend([f"--{key}", str(value)])

        # Determine input source
        if resolved.url:
            # Protocol or profile - pass URL as argument
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

    except ValueError as e:
        click.echo(f"Error: Invalid address syntax: {e}", err=True)
        sys.exit(1)
    except AddressResolutionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
