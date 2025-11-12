"""Put command - write NDJSON to file."""

import io
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
from ..helpers import check_uv_available


@click.command()
@click.argument("output_file")
@pass_context
def put(ctx, output_file):
    """Read NDJSON from stdin, write to file or stdout.

    Supports universal addressing syntax: address[~format][?parameters]

    Examples:
        # Basic files
        jn cat data.csv | jn put output.json          # Auto-detect format
        jn cat data.csv | jn put output.txt~json      # Force JSON format
        jn cat data.json | jn put output.json?indent=4  # Pretty JSON

        # Stdout with format override
        jn cat data.json | jn put "-~table"           # Simple table
        jn cat data.json | jn put "-~table.grid"      # Grid table (shorthand)
        jn cat data.json | jn put "-~json?indent=2"   # Pretty JSON to stdout

        # Table with parameters
        jn cat data.json | jn put "-~table?tablefmt=grid&maxcolwidths=20"
        jn cat data.json | jn put "-~table?tablefmt=markdown&showindex=true"

        # CSV with parameters
        jn cat data.json | jn put "output.csv?delimiter=;&header=false"
    """
    try:
        check_uv_available()

        # Parse address
        addr = parse_address(output_file)

        # Create resolver and resolve address
        resolver = AddressResolver(ctx.plugin_dir, ctx.cache_path)
        resolved = resolver.resolve(addr, mode="write")

        # Build command
        cmd = [
            "uv",
            "run",
            "--script",
            resolved.plugin_path,
            "--mode",
            "write",
        ]

        # Add configuration parameters
        for key, value in resolved.config.items():
            cmd.extend([f"--{key}", str(value)])

        # Prepare stdin for subprocess
        try:
            sys.stdin.fileno()
            stdin_source = sys.stdin
            input_data = None
            text_mode = True
        except (AttributeError, OSError, io.UnsupportedOperation):
            # Not a real file handle (e.g., Click test runner)
            input_data = sys.stdin.read()
            stdin_source = subprocess.PIPE
            text_mode = isinstance(input_data, str)

        # Determine output destination and add URL/headers if needed
        if resolved.url:
            # Protocol or profile destination - pass URL to plugin
            if resolved.headers:
                cmd.extend(["--headers", json.dumps(resolved.headers)])
            cmd.append(resolved.url)

            proc = subprocess.Popen(
                cmd,
                stdin=stdin_source,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=text_mode,
            )

            if input_data is not None:
                proc.stdin.write(input_data)
                proc.stdin.close()

            proc.wait()
        elif addr.type == "stdio":
            # Write to stdout
            proc = subprocess.Popen(
                cmd,
                stdin=stdin_source,
                stdout=sys.stdout,
                stderr=subprocess.PIPE,
                text=text_mode,
            )

            if input_data is not None:
                proc.stdin.write(input_data)
                proc.stdin.close()

            proc.wait()
        else:
            # Write to local file
            with open(addr.base, "w") as outfile:
                proc = subprocess.Popen(
                    cmd,
                    stdin=stdin_source,
                    stdout=outfile,
                    stderr=subprocess.PIPE,
                    text=text_mode,
                )

                if input_data is not None:
                    proc.stdin.write(input_data)
                    proc.stdin.close()

                proc.wait()

        # Check for errors
        if proc.returncode != 0:
            err = proc.stderr.read()
            if not text_mode and isinstance(err, bytes):
                err = err.decode()
            click.echo(f"Error: Writer error: {err}", err=True)
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
