"""Head command - output first N records."""

import sys

import click

from ..context import pass_context
from ..core.pipeline import PipelineError, start_reader
from ..core.streaming import head as stream_head


@click.command()
@click.argument("source", required=False)
@click.option("-n", "--lines", "n", type=int, default=10, help="Number of lines to output")
@pass_context
def head(ctx, source, n):
    """Output first N records from NDJSON stream.

    Examples:
        jn cat data.csv | jn head         # From piped input (first 10)
        jn cat data.csv | jn head -n 5    # First 5 records
        jn head data.csv -n 5             # Directly from file
        jn head data.csv                  # Default: first 10 records
    """
    try:
        if source:
            # Read from file using core pipeline
            proc = start_reader(source, ctx.plugin_dir, ctx.cache_path)
            stream_head(proc.stdout, n, sys.stdout)
            proc.wait()
            proc._jn_infile.close()

            if proc.returncode != 0:
                error_msg = proc.stderr.read()
                click.echo(f"Error: {error_msg}", err=True)
                sys.exit(1)
        else:
            # Read from stdin
            stream_head(sys.stdin, n, sys.stdout)
    except PipelineError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
