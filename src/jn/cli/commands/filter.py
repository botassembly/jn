"""Filter command - apply jq expressions."""

import sys

import click

from ...context import pass_context
from ...core.pipeline import PipelineError, filter_stream


@click.command()
@click.argument("query")
@click.option(
    "--param", "-p",
    multiple=True,
    help="Profile parameter (format: key=value, can be used multiple times)"
)
@pass_context
def filter(ctx, query, param):
    """Filter NDJSON using jq expression or profile.

    QUERY can be either:
    - A jq expression: '.age > 25'
    - A profile reference: '@analytics/pivot'

    Examples:
        # Direct jq expression
        jn cat data.csv | jn filter '.age > 25'

        # Profile with parameters
        jn cat data.csv | jn filter '@analytics/pivot' -p row=product -p col=month
    """
    try:
        # Parse parameters into dict
        params = {}
        for p in param:
            if "=" not in p:
                click.echo(f"Error: Invalid parameter format '{p}'. Use: key=value", err=True)
                sys.exit(1)
            key, value = p.split("=", 1)
            params[key] = value

        # Ensure Click runner stdin/stdout are respected
        filter_stream(
            query,
            ctx.plugin_dir,
            ctx.cache_path,
            params=params if params else None,
            input_stream=sys.stdin,
            output_stream=sys.stdout
        )
    except PipelineError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
