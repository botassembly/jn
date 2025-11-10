"""Cat command - read files and output NDJSON."""

import sys

import click

from ..context import pass_context
from ..core.pipeline import PipelineError, convert, read_source


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
    try:
        if output_file:
            # Two-stage pipeline: source → dest
            convert(input_file, output_file, ctx.plugin_dir, ctx.cache_path)
        else:
            # Single stage: source → stdout
            read_source(input_file, ctx.plugin_dir, ctx.cache_path)
    except PipelineError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
