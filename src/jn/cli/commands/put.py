"""Put command - write NDJSON to file."""

import sys

import click

from ...context import pass_context
from ...core.pipeline import PipelineError, write_destination


@click.command()
@click.argument("output_file")
@click.option("--plugin", help="Explicitly specify plugin to use (e.g., 'tabulate_', 'csv_')")
@click.option("--tablefmt", default="simple", help="Table format for tabulate plugin")
@pass_context
def put(ctx, output_file, plugin, tablefmt):
    """Read NDJSON from stdin, write to file or stdout.

    Examples:
        jn cat data.csv | jn put output.json
        jn cat data.csv | jn put --plugin tabulate_ -
        jn cat data.csv | jn put --plugin tabulate_ --tablefmt grid stdout
    """
    try:
        # Pass the current stdin so Click's runner can feed input
        write_destination(
            output_file,
            ctx.plugin_dir,
            ctx.cache_path,
            input_stream=sys.stdin,
            plugin_name=plugin,
            plugin_config={"tablefmt": tablefmt} if plugin == "tabulate_" else None
        )
    except PipelineError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
