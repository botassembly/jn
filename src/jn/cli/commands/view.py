"""Interactive NDJSON viewer command - launches VisiData."""

import click

from ...context import JNContext
from .vd import vd as vd_command


@click.command()
@click.argument("source", required=False)
@click.option(
    "--filter",
    "-f",
    "filter_expr",
    help="Pre-filter with jq expression before viewing",
)
@click.pass_obj
def view(ctx: JNContext, source: str, filter_expr: str) -> None:
    """View NDJSON data interactively using VisiData.

    This command is an alias for 'jn vd'. Both commands launch VisiData
    for interactive data exploration.

    Requires VisiData to be installed: uv tool install visidata

    \b
    Examples:
        jn cat data.json | jn view
        jn view data.json
        jn view data.json --filter '.age > 30'

    For full options and VisiData reference, see: jn vd --help
    """
    # Delegate to vd command
    ctx_obj = click.get_current_context()
    ctx_obj.invoke(vd_command, source=source, filter_expr=filter_expr)
