"""Head command - output first N records."""

import subprocess
import sys

import click

from ...context import pass_context
from ...core.streaming import head as stream_head
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
def head(ctx, source, n):
    """Output first N records from NDJSON stream.

    Supports universal addressing syntax: address[~format][?parameters]

    Examples:
        # From piped input
        jn cat data.csv | jn head         # First 10 records
        jn cat data.csv | jn head -n 5    # First 5 records

        # Directly from file
        jn head data.csv -n 5             # Auto-detect format
        jn head data.txt~csv -n 10        # Force CSV format
        jn head "data.csv~csv?delimiter=;" -n 5  # With parameters

    Note:
        When passing addresses that start with '-', use '--' to stop
        option parsing before the argument.
    """
    try:
        # Support "jn head N" by treating a numeric first arg as line count
        if source and source.isdigit():
            n = int(source)
            source = None

        if n < 0:
            click.echo("Error: --lines must be >= 0", err=True)
            sys.exit(1)

        if source:
            check_uv_available()

            # Use cat pipeline for address resolution, plugins, and filtering.
            # This keeps head focused purely on stream truncation.
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
            stream_head(cat_proc.stdout, n, sys.stdout)

            # Close our handle to cat stdout so upstream gets SIGPIPE when head finishes.
            cat_proc.stdout.close()
            cat_proc.wait()

            # Check for real errors (not SIGPIPE or spurious exit codes).
            # SIGPIPE (-13) is expected when head closes the pipe before cat finishes.
            # Sometimes subprocesses return 1 without real error output due to timing.
            # We only treat it as a real error if there's actual error message on stderr.
            import signal

            if cat_proc.returncode not in (0, -signal.SIGPIPE):
                assert cat_proc.stderr is not None
                error_msg = cat_proc.stderr.read()
                if error_msg.strip():
                    click.echo(error_msg, err=True)
                    sys.exit(1)
        else:
            # Read from stdin directly
            stream_head(sys.stdin, n, sys.stdout)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
