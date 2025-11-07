"""CLI command: jn show pipeline - display pipeline definition."""

import typer

from jn import config

from .. import ConfigPath
from . import show_app


@show_app.command()
def pipeline(
    name: str,
    jn: ConfigPath = None,
) -> None:
    """Show a pipeline's JSON definition."""
    config.set_config_path(jn)
    item = config.fetch_item("pipelines", name)

    if item is None:
        typer.echo(f"Error: pipeline '{name}' not found", err=True)
        raise typer.Exit(1)

    typer.echo(item.model_dump_json(indent=2, exclude_none=True))
