"""Run command - shorthand for cat."""

import click
from .cat import cat as cat_cmd


@click.command()
@click.argument('input_file')
@click.argument('output_file')
@click.pass_context
def run(ctx, input_file, output_file):
    """Run pipeline from input to output.

    Example:
        jn run data.csv output.json
    """
    # Delegate to cat command
    ctx.invoke(cat_cmd, input_file=input_file, output_file=output_file)
