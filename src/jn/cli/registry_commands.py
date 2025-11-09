"""Common registry command patterns for APIs and filters.

This module provides reusable functions to eliminate duplication
between api.py and filter.py CLI commands.
"""

import json
from typing import Any, Callable, Generic, List, Optional, TypeVar

import typer

from jn import config
from jn.models import Error
from jn.options import ConfigPathType

T = TypeVar("T")


class RegistryCommands(Generic[T]):
    """Reusable registry command handlers for APIs, filters, etc."""

    def __init__(
        self,
        resource_name: str,
        list_func: Callable[[], List[str]],
        get_func: Callable[[str], Optional[T]],
        has_func: Callable[[str], bool],
        remove_attr: str,
    ):
        """Initialize registry commands.

        Args:
            resource_name: Name of resource (e.g., "API", "filter")
            list_func: Function to list all resource names
            get_func: Function to get resource by name
            has_func: Function to check if resource exists
            remove_attr: Config attribute name for removal (e.g., "apis", "filters")
        """
        self.resource_name = resource_name
        self.list_func = list_func
        self.get_func = get_func
        self.has_func = has_func
        self.remove_attr = remove_attr

    def list_resources(self, jn: ConfigPathType) -> None:
        """List all registered resources."""
        config.set_config_path(jn)
        names = self.list_func()
        if not names:
            typer.echo(f"No {self.resource_name}s defined.")
            return
        for name in names:
            typer.echo(name)

    def show_resource(self, name: str, jn: ConfigPathType) -> None:
        """Display details of a registered resource."""
        config.set_config_path(jn)

        resource = self.get_func(name)
        if not resource:
            typer.echo(
                f"Error: {self.resource_name} '{name}' not found", err=True
            )
            raise typer.Exit(1)

        resource_dict = resource.model_dump(exclude_none=True)
        typer.echo(json.dumps(resource_dict, indent=2))

    def remove_resource(
        self, name: str, force: bool, jn: ConfigPathType
    ) -> None:
        """Remove a resource from the registry."""
        config.set_config_path(jn)

        if not self.has_func(name):
            typer.echo(
                f"Error: {self.resource_name} '{name}' not found", err=True
            )
            raise typer.Exit(1)

        if not force:
            confirm = typer.confirm(f"Remove {self.resource_name} '{name}'?")
            if not confirm:
                typer.echo("Cancelled.")
                raise typer.Exit(0)

        # Load config, remove resource, persist
        cfg = config.require().model_copy(deep=True)
        current_list = getattr(cfg, self.remove_attr)
        setattr(
            cfg,
            self.remove_attr,
            [r for r in current_list if r.name != name],
        )
        config.persist(cfg)

        typer.echo(f"Removed {self.resource_name}: {name}")

    def handle_existing_resource(
        self,
        name: str,
        existing: T,
        new_resource: T,
        skip_if_exists: bool,
        yes: bool,
    ) -> bool:
        """Handle confirmation flow when resource already exists.

        Returns:
            True if should proceed with replacement, False if cancelled/skipped
        """
        if skip_if_exists:
            typer.echo(
                f"{self.resource_name} '{name}' already exists, skipping."
            )
            return False

        typer.echo(f"{self.resource_name} '{name}' already exists.", err=True)
        typer.echo()
        typer.echo("BEFORE:")
        typer.echo(
            json.dumps(existing.model_dump(exclude_none=True), indent=2)
        )
        typer.echo()

        typer.echo("AFTER:")
        typer.echo(
            json.dumps(new_resource.model_dump(exclude_none=True), indent=2)
        )
        typer.echo()

        if not yes:
            confirm = typer.confirm(f"Replace existing {self.resource_name}?")
            if not confirm:
                typer.echo("Cancelled.")
                raise typer.Exit(0)

        # Remove existing before adding new
        cfg = config.require().model_copy(deep=True)
        current_list = getattr(cfg, self.remove_attr)
        setattr(
            cfg,
            self.remove_attr,
            [r for r in current_list if r.name != name],
        )
        config.persist(cfg)

        return True

    def handle_add_result(
        self,
        result: Any,
        name: str,
        existing: Optional[T],
        success_attrs: dict[str, str],
    ) -> None:
        """Handle result from add operation and display success message.

        Args:
            result: Result from add operation (Error or resource object)
            name: Resource name
            existing: Previous resource if replacing
            success_attrs: Dict of attribute names to display labels
        """
        if isinstance(result, Error):
            typer.echo(f"Error: {result.message}", err=True)
            raise typer.Exit(1)

        if existing:
            typer.echo(f"Replaced {self.resource_name}: {name}")
        else:
            typer.echo(f"Created {self.resource_name}: {name}")

        # Display success attributes
        for attr, label in success_attrs.items():
            value = getattr(result, attr, None)
            if value is not None:
                if isinstance(value, dict) and hasattr(value, "type"):
                    typer.echo(f"  {label}: {value.type}")
                else:
                    typer.echo(f"  {label}: {value}")
