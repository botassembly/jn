"""CLI command: jn new pipeline - create pipelines."""

from pathlib import Path
from typing import List, Optional

import typer

from ...config import get_config
from ...models import Error
from ...service.new import add_pipeline
from . import new_app


@new_app.command()
def pipeline(
    name: str,
    steps: List[str] = typer.Option(
        ...,
        "--steps",
        help="Pipeline steps in format 'type:ref' (e.g., 'source:echo')",
    ),
    jn: Optional[Path] = typer.Option(
        None,
        help="Path to jn.json config file",
    ),
) -> None:
    """Create a new pipeline."""
    config = get_config(jn)

    result = add_pipeline(config, name, steps)

    if isinstance(result, Error):
        typer.echo(str(result), err=True)
        raise typer.Exit(1)

    typer.echo(f"Created pipeline '{result.name}' with {len(result.steps)} steps")
