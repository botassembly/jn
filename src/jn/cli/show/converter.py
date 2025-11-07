"""CLI command: jn show converter - display converter definition."""

from pathlib import Path
from typing import Optional

import typer

from . import show_app
from ...config import get_converter


@show_app.command()
def converter(
    name: str,
    jn: Optional[Path] = typer.Option(
        None,
        help="Path to jn.json config file",
    ),
) -> None:
    """Show a converter's JSON definition."""
    item = get_converter(name, jn)

    if item is None:
        typer.echo(f"Error: converter '{name}' not found", err=True)
        raise typer.Exit(1)

    typer.echo(item.model_dump_json(indent=2, exclude_none=True))
