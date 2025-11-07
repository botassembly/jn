"""CLI command: jn show target - display target definition."""

from pathlib import Path
from typing import Optional

import typer

from . import show_app
from ...config import get_target


@show_app.command()
def target(
    name: str,
    jn: Optional[Path] = typer.Option(
        None,
        help="Path to jn.json config file",
    ),
) -> None:
    """Show a target's JSON definition."""
    item = get_target(name, jn)

    if item is None:
        typer.echo(f"Error: target '{name}' not found", err=True)
        raise typer.Exit(1)

    typer.echo(item.model_dump_json(indent=2, exclude_none=True))
