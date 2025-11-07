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
    try:
        project = get_config(jn)

        # Find the item by kind and name
        if kind == "source":
            collection = project.sources
        elif kind == "target":
            collection = project.targets
        elif kind == "converter":
            collection = project.converters
        elif kind == "pipeline":
            collection = project.pipelines
        else:
            raise ValueError(f"Unknown kind: {kind}")

        item = next((item for item in collection if item.name == name), None)

        if item is None:
            typer.echo(f"Error: {kind} '{name}' not found", err=True)
            raise typer.Exit(1)

        # Output the item as JSON
        typer.echo(item.model_dump_json(indent=2, exclude_none=True))

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
