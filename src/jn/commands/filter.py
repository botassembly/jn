"""Filter command - apply jq expressions."""

import sys

import click

from ..context import pass_context
from ..core.pipeline import PipelineError, filter_stream


@click.command()
@click.argument("query")
@pass_context
def filter(ctx, query):
    """Filter NDJSON using jq expression.

    Example:
        jn cat data.csv | jn filter '.age > 25'
    """
    try:
        filter_stream(query, ctx.plugin_dir, ctx.cache_path)
    except PipelineError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
