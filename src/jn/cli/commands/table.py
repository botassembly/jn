"""Table command - render NDJSON as formatted tables."""

import json
import signal
import sys

import click


# Handle SIGPIPE gracefully (e.g., when piped to `head`)
signal.signal(signal.SIGPIPE, signal.SIG_DFL)


# All formats supported by tabulate
TABULATE_FORMATS = [
    "plain",
    "simple",
    "github",
    "grid",
    "fancy_grid",
    "fancy_outline",
    "pipe",
    "orgtbl",
    "jira",
    "presto",
    "pretty",
    "psql",
    "rst",
    "mediawiki",
    "moinmoin",
    "youtrack",
    "html",
    "unsafehtml",
    "latex",
    "latex_raw",
    "latex_booktabs",
    "latex_longtable",
    "textile",
    "tsv",
    "rounded_grid",
    "rounded_outline",
    "heavy_grid",
    "heavy_outline",
    "mixed_grid",
    "mixed_outline",
    "double_grid",
    "double_outline",
    "simple_grid",
    "simple_outline",
]


@click.command()
@click.option(
    "-f",
    "--format",
    "tablefmt",
    default="grid",
    help=f"Table format style. Options: {', '.join(TABULATE_FORMATS[:10])}... [default: grid]",
)
@click.option(
    "-w",
    "--width",
    "maxcolwidths",
    type=int,
    help="Maximum column width (text wraps at this width)",
)
@click.option(
    "--index",
    "showindex",
    is_flag=True,
    help="Show row index numbers",
)
@click.option(
    "--no-header",
    "disable_headers",
    is_flag=True,
    help="Hide the header row",
)
@click.option(
    "--numalign",
    type=click.Choice(["left", "right", "center", "decimal"]),
    default="decimal",
    help="Number alignment [default: decimal]",
)
@click.option(
    "--stralign",
    type=click.Choice(["left", "right", "center"]),
    default="left",
    help="String alignment [default: left]",
)
def table(tablefmt, maxcolwidths, showindex, disable_headers, numalign, stralign):
    """Render NDJSON as a formatted table.

    Reads NDJSON from stdin and outputs a formatted table to stdout.
    Tables are for human viewing - output cannot be piped to other jn commands.

    Examples:

        # Basic table (default grid format)
        jn cat data.csv | jn table

        # GitHub markdown (great for README files)
        jn cat data.csv | jn table -f github

        # Fancy Unicode table
        jn cat data.csv | jn table -f fancy_grid

        # Limit column width (wraps text)
        jn cat data.csv | jn table -w 40

        # Show row numbers
        jn cat data.csv | jn table --index

        # Simple format (minimal, clean)
        jn cat data.csv | jn table -f simple

        # Pipeline integration
        jn cat data.csv | jn filter '.active' | jn table

    Supported Formats:
        grid, simple, github, fancy_grid, pipe, psql, rst, html, latex,
        jira, mediawiki, tsv, rounded_grid, heavy_grid, and many more.
        See tabulate documentation for the full list.
    """
    try:
        # Collect records from stdin
        records = []
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                click.echo(f"Error: Invalid JSON: {e}", err=True)
                sys.exit(1)

        if not records:
            # Empty input - nothing to display
            return

        # Import tabulate here to avoid startup cost if not needed
        try:
            from tabulate import tabulate as tabulate_fn
        except ImportError:
            click.echo(
                "Error: tabulate library not installed. "
                "Install with: pip install tabulate",
                err=True,
            )
            sys.exit(1)

        # Validate format
        if tablefmt not in TABULATE_FORMATS:
            click.echo(
                f"Error: Unknown format '{tablefmt}'. "
                f"Available: {', '.join(TABULATE_FORMATS[:10])}...",
                err=True,
            )
            sys.exit(1)

        # Build tabulate options
        headers = "keys" if not disable_headers else []

        # Render table
        result = tabulate_fn(
            records,
            headers=headers,
            tablefmt=tablefmt,
            maxcolwidths=maxcolwidths,
            showindex=showindex,
            numalign=numalign,
            stralign=stralign,
        )

        print(result)

    except BrokenPipeError:
        # Gracefully handle broken pipe (e.g., piping to `head`)
        # Close stdout to avoid further errors
        try:
            sys.stdout.close()
        except BrokenPipeError:
            pass
        sys.exit(0)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
