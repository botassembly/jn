"""Run command - convenience for source to dest conversion."""

import sys

import click

from ..context import pass_context
from ..core.pipeline import PipelineError, convert


@click.command()
@click.argument("input_file")
@click.argument("output_file")
@pass_context
def run(ctx, input_file, output_file):
    """Run pipeline from input to output.

    Convenience command that chains read → write with automatic backpressure.
    Equivalent to: jn cat input | jn put output

    Example:
        jn run data.csv output.json    # CSV → JSON conversion
        jn run data.json output.yaml   # JSON → YAML conversion
    """
    try:
        convert(input_file, output_file, ctx.plugin_dir, ctx.cache_path)
    except PipelineError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
