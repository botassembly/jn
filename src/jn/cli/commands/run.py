"""Run command - convenience for source to dest conversion."""

import json

import subprocess
import sys

import click

from ...addressing import AddressResolutionError, AddressResolver, parse_address
from ...context import pass_context
from ..helpers import check_uv_available


@click.command()
@click.argument("input_file")
@click.argument("output_file")
@pass_context
def run(ctx, input_file, output_file):
    """Run pipeline from input to output.

    Convenience command that chains read → write with automatic backpressure.
    Equivalent to: jn cat input | jn put output

    Supports universal addressing syntax: address[~format][?parameters]

    Examples:
        # Basic conversion
        jn run data.csv output.json                    # CSV → JSON

        # Format override
        jn run data.txt~csv output.json                # Force CSV input

        # With parameters
        jn run "data.csv~csv?delimiter=;" output.json  # Semicolon delimiter
        jn run data.json "output.json?indent=4"        # Pretty JSON output
    """
    try:
        check_uv_available()

        # Parse addresses
        input_addr = parse_address(input_file)
        output_addr = parse_address(output_file)

        # Create resolver and resolve addresses
        resolver = AddressResolver(ctx.plugin_dir, ctx.cache_path)
        input_resolved = resolver.resolve(input_addr, mode="read")
        output_resolved = resolver.resolve(output_addr, mode="write")

        # Build reader command
        reader_cmd = [
            "uv",
            "run",
            "--script",
            input_resolved.plugin_path,
            "--mode",
            "read",
        ]

        # Add reader configuration
        for key, value in input_resolved.config.items():
            reader_cmd.extend([f"--{key}", str(value)])

        # Determine reader input source
        if input_resolved.url:
            # Protocol or profile
            if input_resolved.headers:
                reader_cmd.extend(["--headers", json.dumps(input_resolved.headers)])
            reader_cmd.append(input_resolved.url)
            reader_stdin = subprocess.DEVNULL
            infile = None
        elif input_addr.type == "stdio":
            # Stdin
            reader_stdin = sys.stdin
            infile = None
        else:
            # File
            infile = open(input_addr.base, "r")
            reader_stdin = infile

        # Build writer command
        writer_cmd = [
            "uv",
            "run",
            "--script",
            output_resolved.plugin_path,
            "--mode",
            "write",
        ]

        # Add writer configuration
        for key, value in output_resolved.config.items():
            writer_cmd.extend([f"--{key}", str(value)])

        # Add URL/headers for protocol/profile destinations
        if output_resolved.url:
            if output_resolved.headers:
                writer_cmd.extend(["--headers", json.dumps(output_resolved.headers)])
            writer_cmd.append(output_resolved.url)

        # Determine writer output destination
        if output_resolved.url:
            # Protocol or profile destination - plugin handles remote write
            reader = subprocess.Popen(
                reader_cmd,
                stdin=reader_stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            writer = subprocess.Popen(
                writer_cmd,
                stdin=reader.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Close reader stdout in parent (critical for SIGPIPE)
            reader.stdout.close()

            # Wait for both processes
            writer.wait()
            reader.wait()

            # Close input file if opened
            if infile:
                infile.close()

            # Check for errors
            if writer.returncode != 0:
                error_msg = writer.stderr.read()
                click.echo(f"Error: Writer error: {error_msg}", err=True)
                sys.exit(1)

            if reader.returncode != 0:
                error_msg = reader.stderr.read()
                click.echo(f"Error: Reader error: {error_msg}", err=True)
                sys.exit(1)
        elif output_addr.type == "stdio":
            # Execute two-stage pipeline: reader → writer → stdout
            reader = subprocess.Popen(
                reader_cmd,
                stdin=reader_stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            writer = subprocess.Popen(
                writer_cmd,
                stdin=reader.stdout,
                stdout=sys.stdout,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Close reader stdout in parent (critical for SIGPIPE)
            reader.stdout.close()

            # Wait for both processes
            writer.wait()
            reader.wait()

            # Close input file if opened
            if infile:
                infile.close()

            # Check for errors
            if writer.returncode != 0:
                error_msg = writer.stderr.read()
                click.echo(f"Error: Writer error: {error_msg}", err=True)
                sys.exit(1)

            if reader.returncode != 0:
                error_msg = reader.stderr.read()
                click.echo(f"Error: Reader error: {error_msg}", err=True)
                sys.exit(1)
        else:
            # Write to file
            with open(output_addr.base, "w") as outfile:
                reader = subprocess.Popen(
                    reader_cmd,
                    stdin=reader_stdin,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                writer = subprocess.Popen(
                    writer_cmd,
                    stdin=reader.stdout,
                    stdout=outfile,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                # Close reader stdout in parent (critical for SIGPIPE)
                reader.stdout.close()

                # Wait for both processes
                writer.wait()
                reader.wait()

                # Close input file if opened
                if infile:
                    infile.close()

                # Check for errors
                if writer.returncode != 0:
                    error_msg = writer.stderr.read()
                    click.echo(f"Error: Writer error: {error_msg}", err=True)
                    sys.exit(1)

                if reader.returncode != 0:
                    error_msg = reader.stderr.read()
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
