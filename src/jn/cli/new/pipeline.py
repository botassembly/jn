"""CLI command: jn new pipeline - create pipelines."""

import typer

from jn import config

from .. import ConfigPath
from . import new_app


@new_app.command()
def pipeline(
    name: str,
    steps: list[str] = typer.Option(
        ...,
        "--steps",
        help="Pipeline steps in format 'type:ref' (e.g., 'source:echo')",
    ),
    jn: ConfigPath = None,
) -> None:
    """Create a new pipeline."""
    config.set_config_path(jn)

    result = config.add_pipeline(name, steps)

    if isinstance(result, config.Error):
        typer.echo(str(result), err=True)
        raise typer.Exit(1)

    typer.echo(
        f"Created pipeline '{result.name}' with {len(result.steps)} steps"
    )
