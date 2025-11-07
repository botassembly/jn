"""CLI command: jn new pipeline - create pipelines."""

from pathlib import Path
from typing import List, Optional

import typer

from ...config import get_config
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

    add_pipeline(
        config=config,
        jn_path=jn,
        name=name,
        steps=steps,
    )

    typer.echo(f"Created pipeline '{name}' with {len(steps)} steps")
