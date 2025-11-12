"""Tail command - output last N records."""

import sys

import click

from ...context import pass_context
from ...core.pipeline import PipelineError, start_reader
from ...core.streaming import tail as stream_tail


@click.command()
@click.argument("source", required=False)
@click.option(
    "-n",
    "--lines",
    "n",
    type=int,
    default=10,
    help="Number of lines to output",
)
@pass_context
def tail(ctx, source, n):
    """Output last N records from NDJSON stream.

    Examples:
        jn cat data.csv | jn tail         # From piped input (last 10)
        jn cat data.csv | jn tail -n 5    # Last 5 records
        jn tail data.csv -n 5             # Directly from file
        jn tail data.csv                  # Default: last 10 records
    """
    try:
        # Support "jn tail N" by treating a numeric first arg as line count
        if source and source.isdigit():
            n = int(source)
            source = None

        if source:
            # Read from file using core pipeline
            proc = start_reader(source, ctx.plugin_dir, ctx.cache_path)
            stream_tail(proc.stdout, n, sys.stdout)
            proc.wait()

            # Close file handle if present
            infile = getattr(proc, "_jn_infile", None)
            if infile is not None:
                infile.close()

            # If there was a previous stage (e.g., protocol raw), check it
            prev = getattr(proc, "_jn_prev_proc", None)
            if prev is not None:
                prev.wait()
                if prev.returncode != 0:
                    perr = prev.stderr.read()
                    if isinstance(perr, bytes):
                        try:
                            perr = perr.decode()
                        except Exception:
                            pass
                    click.echo(f"Error: {perr}", err=True)
                    sys.exit(1)

            if proc.returncode != 0:
                error_msg = proc.stderr.read()
                if isinstance(error_msg, bytes):
                    try:
                        error_msg = error_msg.decode()
                    except Exception:
                        pass
                click.echo(f"Error: {error_msg}", err=True)
                sys.exit(1)
        else:
            # Read from stdin
            stream_tail(sys.stdin, n, sys.stdout)
    except PipelineError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
