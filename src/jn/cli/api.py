"""CLI command: jn api - manage APIs in the registry."""

from typing import List, Optional

import typer

from jn import config
from jn.cli.registry_commands import RegistryCommands
from jn.cli.validation import (
    parse_headers,
    validate_api_type,
    validate_auth_type,
)
from jn.options import ConfigPath, ConfigPathType

app = typer.Typer(help="Manage API configurations")

# Create registry command helper
_registry = RegistryCommands(
    resource_name="API",
    list_func=config.api_names,
    get_func=config.get_api,
    has_func=config.has_api,
    remove_attr="apis",
)


@app.callback(invoke_without_command=True)
def default(ctx: typer.Context, jn: ConfigPathType = ConfigPath):
    """List all registered APIs (default action)."""
    if ctx.invoked_subcommand is None:
        _registry.list_resources(jn)


@app.command()
def add(
    name: str = typer.Argument(..., help="Unique name for the API"),
    base_url: Optional[str] = typer.Option(
        None, "--base-url", help="Base URL for REST API"
    ),
    auth_type: Optional[str] = typer.Option(
        None, "--auth", help="Auth type: bearer, basic, oauth2, api_key"
    ),
    token: Optional[str] = typer.Option(
        None, "--token", help="Auth token (supports ${env:VAR})"
    ),
    username: Optional[str] = typer.Option(
        None, "--username", help="Username for basic auth or DB user"
    ),
    password: Optional[str] = typer.Option(
        None, "--password", help="Password (supports ${env:VAR})"
    ),
    header: Optional[List[str]] = typer.Option(
        None, "--header", help="HTTP header in KEY:VALUE format"
    ),
    source_method: str = typer.Option(
        "GET",
        "--source-method",
        help="Default HTTP method when used as source",
    ),
    target_method: str = typer.Option(
        "POST",
        "--target-method",
        help="Default HTTP method when used as target",
    ),
    api_type: str = typer.Option(
        "rest",
        "--type",
        help="API type: rest, graphql, postgres, mysql, s3, gcs, kafka",
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
        False, "--skip-if-exists", help="Skip if API already exists"
    ),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Add a new API configuration.

    Examples:
      jn api add github --base-url https://api.github.com --auth bearer --token '${env:GITHUB_TOKEN}'
      jn api add mydb --type postgres --host localhost --username admin --password '${env:DB_PASSWORD}'
    """
    config.set_config_path(jn)

    # Validate and parse inputs
    validated_api_type = validate_api_type(api_type)
    validated_auth_type = validate_auth_type(auth_type) if auth_type else None
    headers = parse_headers(header) if header else {}

    # Check if API already exists
    existing = config.get_api(name)
    if existing:
        # Build new API config for preview
        from jn.models import Api, AuthConfig

        auth = None
        if validated_auth_type:
            auth = AuthConfig(
                type=validated_auth_type,
                token=token,
                username=username,
                password=password,
            )

        new_api = Api(
            name=name,
            type=validated_api_type,
            base_url=base_url,
            auth=auth,
            headers=headers or {},
            source_method=source_method,
            target_method=target_method,
        )

        # Handle existing resource confirmation flow
        should_proceed = _registry.handle_existing_resource(
            name, existing, new_api, skip_if_exists, yes
        )
        if not should_proceed:
            return

    result = config.add_api(
        name=name,
        api_type=validated_api_type,
        base_url=base_url,
        auth_type=validated_auth_type,
        token=token,
        username=username,
        password=password,
        headers=headers if headers else None,
        source_method=source_method,
        target_method=target_method,
    )

    # Handle add result
    _registry.handle_add_result(
        result,
        name,
        existing,
        {
            "type": "Type",
            "base_url": "Base URL",
            "auth": "Auth",
        },
    )


@app.command()
def show(
    name: str = typer.Argument(..., help="API name to display"),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Display details of a registered API.

    Example:
      jn api show github
    """
    _registry.show_resource(name, jn)


@app.command()
def update(
    name: str = typer.Argument(..., help="API name to update"),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Update an existing API configuration (opens in $EDITOR).

    Example:
      jn api update github
    """
    typer.echo("TODO: Implement update command (edit in $EDITOR)", err=True)
    raise typer.Exit(1)


@app.command()
def rm(
    name: str = typer.Argument(..., help="API name to remove"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Skip confirmation"
    ),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Remove an API from the registry.

    Example:
      jn api rm github
      jn api rm github --force
    """
    _registry.remove_resource(name, force, jn)
