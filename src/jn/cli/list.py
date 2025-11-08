"""CLI command: jn list - list items by kind.

Simplified for apis and filters architecture.
"""

import typer

from jn import ConfigPath, ConfigPathType, config

from . import app


@app.command()
def list(
    kind: config.CollectionName,
    jn: ConfigPathType = ConfigPath,
) -> None:
    """List items by kind (apis, filters).

    Examples:
      jn list apis
      jn list filters
    """
    config.set_config_path(jn)

    names = config.list_items(kind)
    if not names:
        typer.echo(f"No {kind} defined.")
        return

    for name in names:
        typer.echo(name)
