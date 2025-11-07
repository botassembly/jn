"""CLI command: jn run - execute a pipeline."""

import sys
from pathlib import Path
from typing import Optional

import typer

from ..config import get_config
from ..service.pipeline import run_pipeline
from . import app


@app.command()
def run(
    pipeline: str,
    jn: Optional[str] = typer.Option(None, "--jn"),
) -> None:
    """Execute a pipeline (source → converters → target)."""
    path = Path(jn) if jn else None
    project = get_config(path)

    try:
        output = run_pipeline(project, pipeline, {})
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
