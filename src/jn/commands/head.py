"""Head command - first N records."""

import sys

import click


@click.command()
@click.argument("n", type=int, default=10)
def head(n):
    """Output first N records from NDJSON stream.

    Example:
        jn cat data.csv | jn head 10
    """
    count = 0
    for line in sys.stdin:
        if count >= n:
            break
        click.echo(line, nl=False)
        count += 1
