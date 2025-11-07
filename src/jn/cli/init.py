"""CLI command: jn init - create a minimal jn.json file."""

from pathlib import Path

import typer

from jn import ConfigPath, ConfigPathType
from jn.home import save_json
from jn.models import Config

from . import app


@app.command()
def init(
    jn: ConfigPathType = ConfigPath,
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing config file",
    ),
) -> None:
    """Create a minimal jn.json configuration file."""
    path = Path(jn) if jn else Path.cwd() / "jn.json"

    if path.exists() and not force:
        typer.echo(
            f"Error: {path} already exists. Use --force to overwrite.",
            err=True,
        )
        raise typer.Exit(code=1)

    config_obj = Config(version="0.1", name=path.parent.name or "config")

    save_json(path, config_obj.model_dump(mode="json"))
    typer.echo(f"Created {path}")
