"""CLI command: jn show source - display source definition."""

from pathlib import Path
from typing import Optional

import typer

from . import show_app
from ...config import get_source


@show_app.command()
def source(
    name: str,
    jn: Optional[Path] = typer.Option(
        None,
        help="Path to jn.json config file",
    ),
) -> None:
    """Show a source's JSON definition."""
    item = get_source(name, jn)

    if item is None:
        typer.echo(f"Error: source '{name}' not found", err=True)
        raise typer.Exit(1)

    typer.echo(item.model_dump_json(indent=2, exclude_none=True))
