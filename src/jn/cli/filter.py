"""CLI command: jn filter - manage filters in the registry."""

from typing import Optional

import typer

from jn import config
from jn.cli.registry_commands import RegistryCommands
from jn.options import ConfigPath, ConfigPathType

app = typer.Typer(help="Manage filter configurations")

# Create registry command helper
_registry = RegistryCommands(
    resource_name="filter",
    list_func=config.filter_names,
    get_func=config.get_filter,
    has_func=config.has_filter,
    remove_attr="filters",
)


@app.callback(invoke_without_command=True)
def default(ctx: typer.Context, jn: ConfigPathType = ConfigPath):
    """List all registered filters (default action)."""
    if ctx.invoked_subcommand is None:
        _registry.list_resources(jn)


@app.command()
def add(
    name: str = typer.Argument(..., help="Unique name for the filter"),
    query: str = typer.Option(..., "--query", help="jq expression to apply"),
    description: Optional[str] = typer.Option(
        None, "--description", help="Human-readable description"
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "--force",
        "-y",
        "-f",
        help="Skip confirmation when replacing",
    ),
    skip_if_exists: bool = typer.Option(
        False, "--skip-if-exists", help="Skip if filter already exists"
    ),
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
        # Build new filter config for preview
        from jn.models import Filter

        new_filter = Filter(
            name=name,
            query=query,
            description=description,
        )

        # Handle existing resource confirmation flow
        should_proceed = _registry.handle_existing_resource(
            name, existing, new_filter, skip_if_exists, yes
        )
        if not should_proceed:
            return

    result = config.add_filter(
        name=name,
        query=query,
        description=description,
    )

    # Handle add result
    _registry.handle_add_result(
        result,
        name,
        existing,
        {
            "query": "Query",
            "description": "Description",
        },
    )


@app.command()
def show(
    name: str = typer.Argument(..., help="Filter name to display"),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Display details of a registered filter.

    Example:
      jn filter show high-value
    """
    _registry.show_resource(name, jn)


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
    force: bool = typer.Option(
        False, "--force", "-f", help="Skip confirmation"
    ),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Remove a filter from the registry.

    Example:
      jn filter rm high-value
      jn filter rm high-value --force
    """
    _registry.remove_resource(name, force, jn)
