"""CLI command: jn show target - display target definition."""

import typer

from jn import config

from .. import ConfigPath
from . import show_app


@show_app.command()
def target(
    name: str,
    jn: ConfigPath = None,
) -> None:
    """Show a target's JSON definition."""
    config.set_config_path(jn)
    item = config.fetch_item("targets", name)

    if item is None:
        typer.echo(f"Error: target '{name}' not found", err=True)
        raise typer.Exit(1)

    typer.echo(item.model_dump_json(indent=2, exclude_none=True))
