"""CLI command: jn filter - manage filters in the registry."""

import json
from typing import Optional

import typer

from jn import config
from jn.models import Error
from jn.options import ConfigPath, ConfigPathType

app = typer.Typer(help="Manage filter configurations")


@app.callback(invoke_without_command=True)
def default(ctx: typer.Context, jn: ConfigPathType = ConfigPath):
    """List all registered filters (default action)."""
    if ctx.invoked_subcommand is None:
        config.set_config_path(jn)
        names = config.filter_names()
        if not names:
            typer.echo("No filters defined.")
            return
        for name in names:
            typer.echo(name)


@app.command()
def add(
    name: str = typer.Argument(..., help="Unique name for the filter"),
    query: str = typer.Option(..., "--query", help="jq expression to apply"),
    description: Optional[str] = typer.Option(None, "--description", help="Human-readable description"),
    yes: bool = typer.Option(False, "--yes", "--force", "-y", "-f", help="Skip confirmation when replacing"),
    skip_if_exists: bool = typer.Option(False, "--skip-if-exists", help="Skip if filter already exists"),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Add a new filter (jq transformation).

    Examples:
      jn filter add high-value --query 'select(.amount > 1000)'
      jn filter add by-category --query 'group_by(.category) | map({category: .[0].category, total: map(.amount) | add})'
    """
    config.set_config_path(jn)

    # Check if filter already exists
    existing = config.get_filter(name)
    if existing:
        if skip_if_exists:
            typer.echo(f"Filter '{name}' already exists, skipping.")
            return

        typer.echo(f"Filter '{name}' already exists.", err=True)
        typer.echo()
        typer.echo("BEFORE:")
        typer.echo(json.dumps(existing.model_dump(exclude_none=True), indent=2))
        typer.echo()

        # Build new filter config for preview
        from jn.models import Filter

        new_filter = Filter(
            name=name,
            query=query,
            description=description,
        )

        typer.echo("AFTER:")
        typer.echo(json.dumps(new_filter.model_dump(exclude_none=True), indent=2))
        typer.echo()

        if not yes:
            confirm = typer.confirm("Replace existing filter?")
            if not confirm:
                typer.echo("Cancelled.")
                raise typer.Exit(0)

        # Remove existing before adding new
        cfg = config.require().model_copy(deep=True)
        cfg.filters = [f for f in cfg.filters if f.name != name]
        config.persist(cfg)

    result = config.add_filter(
        name=name,
        query=query,
        description=description,
    )

    if isinstance(result, Error):
        typer.echo(f"Error: {result.message}", err=True)
        raise typer.Exit(1)

    if existing:
        typer.echo(f"Replaced filter: {name}")
    else:
        typer.echo(f"Created filter: {name}")
    typer.echo(f"  Query: {result.query}")
    if result.description:
        typer.echo(f"  Description: {result.description}")


@app.command()
def show(
    name: str = typer.Argument(..., help="Filter name to display"),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Display details of a registered filter.

    Example:
      jn filter show high-value
    """
    config.set_config_path(jn)

    filter_obj = config.get_filter(name)
    if not filter_obj:
        typer.echo(f"Error: Filter '{name}' not found", err=True)
        raise typer.Exit(1)

    filter_dict = filter_obj.model_dump(exclude_none=True)
    typer.echo(json.dumps(filter_dict, indent=2))


@app.command()
def update(
    name: str = typer.Argument(..., help="Filter name to update"),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Update an existing filter (opens in $EDITOR).

    Example:
      jn filter update high-value
    """
    typer.echo("TODO: Implement update command (edit in $EDITOR)", err=True)
    raise typer.Exit(1)


@app.command()
def rm(
    name: str = typer.Argument(..., help="Filter name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Remove a filter from the registry.

    Example:
      jn filter rm high-value
      jn filter rm high-value --force
    """
    config.set_config_path(jn)

    if not config.has_filter(name):
        typer.echo(f"Error: Filter '{name}' not found", err=True)
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Remove filter '{name}'?")
        if not confirm:
            typer.echo("Cancelled.")
            raise typer.Exit(0)

    # Load config, remove filter, persist
    cfg = config.require().model_copy(deep=True)
    cfg.filters = [f for f in cfg.filters if f.name != name]
    config.persist(cfg)

    typer.echo(f"Removed filter: {name}")
