"""CLI command: jn list - list items by kind."""

from typing import Literal, Optional

import typer

from ..config import get_config
from . import app


@app.command()
def list(
    kind: Literal["sources", "targets", "converters", "pipelines"],
    jn: Optional[str] = typer.Option(None, "--jn"),
) -> None:
    """List items by kind (sources, targets, converters, pipelines)."""
    project = get_config(jn)

    items = getattr(project, kind)
    if not items:
        typer.echo(f"No {kind} defined.")
        return

    for item in items:
        typer.echo(item.name)
