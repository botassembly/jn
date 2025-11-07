"""CLI command: jn run - execute a pipeline."""

import sys
from pathlib import Path
from typing import Optional

import typer

from ..config import get_config
from ..service.pipeline import run_pipeline


def register(app: typer.Typer) -> None:
    """Register the run command with the Typer app."""

    @app.command()
    def run(
        pipeline: str = typer.Argument(
            ..., help="Name of pipeline to execute"
        ),
        jn: Optional[str] = typer.Option(
            None, "--jn", help="Path to jn.json file"
        ),
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
