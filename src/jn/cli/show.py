"""CLI command: show item by kind and name."""

from pathlib import Path
from typing import Literal, Optional

import typer

from ..config import get_config
from . import app


@app.command()
def show(
    kind: Literal["source", "target", "converter", "pipeline"],
    name: str,
    jn: Optional[Path] = typer.Option(
        None, help="Path to jn.json config file"
    ),
) -> None:
    """Show a single item's JSON definition."""
    config = get_config(jn)

    # Get the item using helper methods
    if kind == "source":
        item = config.get_source(name)
    elif kind == "target":
        item = config.get_target(name)
    elif kind == "converter":
        item = config.get_converter(name)
    else:  # pipeline
        item = config.get_pipeline(name)

    if item is None:
        typer.echo(f"Error: {kind} '{name}' not found", err=True)
        raise typer.Exit(1)

    typer.echo(item.model_dump_json(indent=2, exclude_none=True))
