"""Tail command - output last N records."""

import subprocess
import sys

import click

from ...context import pass_context
from ...core.streaming import tail as stream_tail
from ...process_utils import popen_with_validation
from ..helpers import build_subprocess_env_for_coverage, check_uv_available

JN_CLI = [sys.executable, "-m", "jn.cli.main"]


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

    Supports universal addressing syntax: address[~format][?parameters]

    Examples:
        # From piped input
        jn cat data.csv | jn tail         # Last 10 records
        jn cat data.csv | jn tail -n 5    # Last 5 records

        # Directly from file
        jn tail data.csv -n 5             # Auto-detect format
        jn tail data.txt~csv -n 10        # Force CSV format
        jn tail "data.csv~csv?delimiter=;" -n 5  # With parameters

    Note:
        When passing addresses that start with '-', use '--' to stop
        option parsing before the argument.
    """
    try:
        # Support "jn tail N" by treating a numeric first arg as line count
        if source and source.isdigit():
            n = int(source)
            source = None

        if n < 0:
            click.echo("Error: --lines must be >= 0", err=True)
            sys.exit(1)

        if source:
            check_uv_available()

            # Use cat pipeline for address resolution, plugins, and filtering.
            # Tail only concerns itself with the last N records.
            cmd = [*JN_CLI, "cat", source]
            stdin_source = (
                sys.stdin if source.startswith("-") else subprocess.DEVNULL
            )
            cat_proc = popen_with_validation(
                cmd,
                stdin=stdin_source,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=build_subprocess_env_for_coverage(),
            )

            assert cat_proc.stdout is not None
            stream_tail(cat_proc.stdout, n, sys.stdout)

            # Close our handle to cat stdout so upstream completes cleanly.
            cat_proc.stdout.close()
            cat_proc.wait()

            if cat_proc.returncode != 0:
                assert cat_proc.stderr is not None
                error_msg = cat_proc.stderr.read()
                click.echo(error_msg, err=True)
                sys.exit(1)
        else:
            # Read from stdin
            stream_tail(sys.stdin, n, sys.stdout)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
