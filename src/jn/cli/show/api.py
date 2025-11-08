"""CLI command: jn show api"""

import json

import typer

from jn import config
from jn.options import ConfigPath, ConfigPathType


def show_api(
    name: str = typer.Argument(..., help="API name to display"),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Display details of a registered API.

    Example:
      jn show api github
    """

    config.set_config_path(jn)

    api = config.get_api(name)
    if not api:
        typer.echo(f"Error: API '{name}' not found", err=True)
        raise typer.Exit(1)

    # Pretty print the API configuration
    api_dict = api.model_dump(exclude_none=True)
    typer.echo(json.dumps(api_dict, indent=2))
