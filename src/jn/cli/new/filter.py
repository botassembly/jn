"""CLI command: jn new filter"""

from typing import Optional

import typer

from jn import config
from jn.models import Error
from jn.options import ConfigPath, ConfigPathType


def new_filter(
    name: str = typer.Argument(..., help="Unique name for the filter"),
    query: str = typer.Option(..., "--query", help="jq expression to apply"),
    description: Optional[str] = typer.Option(None, "--description", help="Human-readable description"),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Create a new filter (jq transformation).

    Filters apply jq queries to transform JSON/NDJSON data.

    Examples:

      # Simple filter
      jn new filter high-value --query 'select(.amount > 1000)'

      # Aggregation filter
      jn new filter by-category --query 'group_by(.category) | map({category: .[0].category, total: map(.amount) | add})'

      # With description
      jn new filter active-users --query 'select(.active == true)' --description 'Filter only active users'
    """

    config.set_config_path(jn)

    result = config.add_filter(
        name=name,
        query=query,
        description=description,
    )

    if isinstance(result, Error):
        typer.echo(f"Error: {result.message}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Created filter: {name}")
    typer.echo(f"  Query: {result.query}")
    if result.description:
        typer.echo(f"  Description: {result.description}")
