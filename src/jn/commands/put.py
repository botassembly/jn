"""Put command - write NDJSON to file."""

import sys

import click

from ..context import pass_context
from ..core.pipeline import PipelineError, write_destination


@click.command()
@click.argument("output_file")
@pass_context
def put(ctx, output_file):
    """Read NDJSON from stdin, write to file.

    Example:
        jn cat data.csv | jn put output.json
    """
    try:
        write_destination(output_file, ctx.plugin_dir, ctx.cache_path)
    except PipelineError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
