"""Tail command - last N records."""

import sys

import click


@click.command()
@click.argument("n", type=int, default=10)
def tail(n):
    """Output last N records from NDJSON stream.

    Example:
        jn cat data.csv | jn tail 10
    """
    buffer = []
    for line in sys.stdin:
        buffer.append(line)
        if len(buffer) > n:
            buffer.pop(0)

    for line in buffer:
        click.echo(line, nl=False)
