"""CLI command: jn list - list items by kind."""

from pathlib import Path
from typing import Literal, Optional

import typer

from ..config import get_config


def register(app: typer.Typer) -> None:
    """Register the list command with the Typer app."""

    @app.command()
    def list(
        kind: Literal["sources", "targets", "converters", "pipelines"] = typer.Argument(
            ..., help="Type of items to list"
        ),
        jn: Optional[str] = typer.Option(None, "--jn", help="Path to jn.json file"),
    ) -> None:
        """List items by kind (sources, targets, converters, pipelines)."""
        path = Path(jn) if jn else None
        project = get_config(path)

        items = {
            "sources": project.sources,
            "targets": project.targets,
            "converters": project.converters,
            "pipelines": project.pipelines,
        }[kind]

        if not items:
            typer.echo(f"No {kind} defined.")
            return

        for item in items:
            typer.echo(item.name)
