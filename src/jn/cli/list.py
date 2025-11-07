"""CLI command: jn list - list items by kind."""

from pathlib import Path
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
    path = Path(jn) if jn else None
    project = get_config(path)

    items = getattr(project, kind)
    if not items:
        typer.echo(f"No {kind} defined.")
        return

    for item in items:
        typer.echo(item.name)
