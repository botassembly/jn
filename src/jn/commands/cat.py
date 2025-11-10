"""Cat command - read files."""

import subprocess
import sys

import click

from ..cli import pass_context
from ..discovery import get_cached_plugins
from ..registry import build_registry


@click.command()
@click.argument("input_file")
@click.argument("output_file", required=False)
@pass_context
def cat(ctx, input_file, output_file):
    """Read file and output NDJSON.

    Examples:
        jn cat data.csv              # Output NDJSON to stdout
        jn cat data.csv output.json  # Convert CSV to JSON
    """
    # Load plugins
    plugins = get_cached_plugins(ctx.plugin_dir, ctx.cache_path)
    registry = build_registry(plugins)

    # Resolve input plugin
    input_plugin_name = registry.match(input_file)
    if not input_plugin_name:
        click.echo(f"Error: No plugin found for {input_file}", err=True)
        sys.exit(1)

    input_plugin = plugins[input_plugin_name]

    if output_file:
        # Two-stage pipeline
        output_plugin_name = registry.match(output_file)
        if not output_plugin_name:
            click.echo(f"Error: No plugin found for {output_file}", err=True)
            sys.exit(1)

        output_plugin = plugins[output_plugin_name]

        # Start reader
        with open(input_file) as infile:
            reader = subprocess.Popen(
                [sys.executable, input_plugin.path, "--mode", "read"],
                stdin=infile,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Start writer
            with open(output_file, "w") as outfile:
                writer = subprocess.Popen(
                    [sys.executable, output_plugin.path, "--mode", "write"],
                    stdin=reader.stdout,
                    stdout=outfile,
                    stderr=subprocess.PIPE,
                )

                # Close reader stdout in parent (for SIGPIPE)
                reader.stdout.close()

                # Wait for both processes
                writer.wait()
                reader.wait()

                # Check errors
                if writer.returncode != 0:
                    error_msg = writer.stderr.read().decode()
                    click.echo(f"Writer error: {error_msg}", err=True)
                    sys.exit(1)

                if reader.returncode != 0:
                    error_msg = reader.stderr.read().decode()
                    click.echo(f"Reader error: {error_msg}", err=True)
                    sys.exit(1)
    else:
        # Single stage to stdout
        with open(input_file) as infile:
            reader = subprocess.Popen(
                [sys.executable, input_plugin.path, "--mode", "read"],
                stdin=infile,
                stderr=subprocess.PIPE,
            )

            reader.wait()

            if reader.returncode != 0:
                error_msg = reader.stderr.read().decode()
                click.echo(f"Error: {error_msg}", err=True)
                sys.exit(1)
