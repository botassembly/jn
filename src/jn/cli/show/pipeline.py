"""CLI command: jn show pipeline - display pipeline definition."""

from pathlib import Path
from typing import Optional

import typer

from . import show_app
from ...config import get_pipeline


@show_app.command()
def pipeline(
    name: str,
    jn: Optional[Path] = typer.Option(
        None,
        help="Path to jn.json config file",
    ),
) -> None:
    """Show a pipeline's JSON definition."""
    item = get_pipeline(name, jn)

    if item is None:
        typer.echo(f"Error: pipeline '{name}' not found", err=True)
        raise typer.Exit(1)

    typer.echo(item.model_dump_json(indent=2, exclude_none=True))
