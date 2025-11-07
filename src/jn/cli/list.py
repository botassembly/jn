"""CLI command: jn list - list items by kind."""

import typer

from jn import ConfigPath, ConfigPathType, config

from . import app


@app.command()
def list(
    kind: config.CollectionName,
    jn: ConfigPathType = ConfigPath,
) -> None:
    """List items by kind (sources, targets, converters, pipelines)."""
    config.set_config_path(jn)

    names = config.list_items(kind)
    if not names:
        typer.echo(f"No {kind} defined.")
        return

    for name in names:
        typer.echo(name)
