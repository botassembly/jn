"""JN CLI main entry point with global options."""

import sys
import os
import click
from pathlib import Path
from .context import JNContext, pass_context


@click.group(context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
@click.option('--home', type=click.Path(), help='JN home directory (overrides $JN_HOME)')
@click.pass_context
def cli(ctx, home):
    """JN v5 - Agent-native ETL with NDJSON pipelines."""
    ctx.ensure_object(JNContext)

    # Determine JN_HOME priority: --home > $JN_HOME > default
    if home:
        ctx.obj.home = Path(home)
    elif 'JN_HOME' in os.environ:
        ctx.obj.home = Path(os.environ['JN_HOME'])
    else:
        ctx.obj.home = None  # Use built-in plugins

    # Set paths
    if ctx.obj.home:
        ctx.obj.plugin_dir = ctx.obj.home / 'plugins'
        ctx.obj.cache_path = ctx.obj.home / 'cache.json'
    else:
        # Use built-in plugins
        ctx.obj.plugin_dir = Path(__file__).parent / 'plugins'
        ctx.obj.cache_path = Path(__file__).parent / 'cache.json'


# Register commands at module level so tests can import cli with commands attached
from .commands import cat, put, run, filter, head, tail, plugin

cli.add_command(cat.cat)
cli.add_command(put.put)
cli.add_command(run.run)
cli.add_command(filter.filter)
cli.add_command(head.head)
cli.add_command(tail.tail)
cli.add_command(plugin.plugin)


def main():
    """Entry point for CLI."""
    cli()


if __name__ == '__main__':
    main()
