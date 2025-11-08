"""CLI command: jn show filter"""

import json

import typer

from jn import config
from jn.options import ConfigPath, ConfigPathType


def show_filter(
    name: str = typer.Argument(..., help="Filter name to display"),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Display details of a registered filter.

    Example:
      jn show filter high-value
    """

    config.set_config_path(jn)

    filter_obj = config.get_filter(name)
    if not filter_obj:
        typer.echo(f"Error: Filter '{name}' not found", err=True)
        raise typer.Exit(1)

    # Pretty print the filter configuration
    filter_dict = filter_obj.model_dump(exclude_none=True)
    typer.echo(json.dumps(filter_dict, indent=2))
