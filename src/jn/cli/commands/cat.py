"""Cat command - read files and output NDJSON."""

import sys

import click

from ...context import pass_context
from ...core.pipeline import PipelineError, read_source


@click.command()
@click.argument("input_file")
@pass_context
def cat(ctx, input_file):
    """Read file and output NDJSON to stdout only.

    Examples:
        jn cat data.csv                        # Output NDJSON to stdout
        jn cat data.csv | jn put output.json   # Pipe to put for conversion
        jn run data.csv output.json            # Direct conversion (read→write)
    """
    try:
        # Pass the current stdout so Click's runner can capture it
        read_source(input_file, ctx.plugin_dir, ctx.cache_path, output_stream=sys.stdout)
    except PipelineError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
