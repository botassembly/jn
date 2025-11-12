"""JN CLI main entry point with global options."""

import click

from ..context import JNContext, resolve_home


@click.group(
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True)
)
@click.option(
    "--home", type=click.Path(), help="JN home directory (overrides $JN_HOME)"
)
@click.pass_context
def cli(ctx, home):
    """JN - Agent-native ETL with NDJSON pipelines."""
    ctx.ensure_object(JNContext)

    # Resolve plugin home and paths once
    paths = resolve_home(home)
    ctx.obj.home = paths.home_dir
    ctx.obj.plugin_dir = paths.plugin_dir
    ctx.obj.cache_path = paths.cache_path


# Register commands at module level so tests can import cli with commands attached
from .commands.cat import cat
from .commands.check import check
from .commands.filter import filter
from .commands.head import head
from .commands.put import put
from .commands.run import run
from .commands.tail import tail
from .plugins import plugin

cli.add_command(cat)
cli.add_command(put)
cli.add_command(run)
cli.add_command(filter)
cli.add_command(head)
cli.add_command(tail)
cli.add_command(check)
cli.add_command(plugin)


def main():
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
