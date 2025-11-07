"""CLI command: jn init - create a minimal jn.json file."""

from pathlib import Path
from typing import Optional

import typer

from ..home import save_json
from . import app


@app.command()
def init(
    jn: Optional[str] = typer.Option(None, "--jn"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Create a minimal jn.json configuration file."""
    path = Path(jn) if jn else Path.cwd() / "jn.json"

    if path.exists() and not force:
        typer.echo(
            f"Error: {path} already exists. Use --force to overwrite.",
            err=True,
        )
        raise typer.Exit(code=1)

    minimal_project = {
        "version": "0.1",
        "name": path.parent.name or "project",
        "sources": [],
        "converters": [],
        "targets": [],
        "pipelines": [],
    }

    save_json(path, minimal_project)
    typer.echo(f"Created {path}")
