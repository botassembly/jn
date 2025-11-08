"""CLI command: jn api - manage APIs in the registry."""

import json
from typing import List, Optional

import typer

from jn import config
from jn.models import Error
from jn.options import ConfigPath, ConfigPathType

app = typer.Typer(help="Manage API configurations")


@app.callback(invoke_without_command=True)
def default(ctx: typer.Context, jn: ConfigPathType = ConfigPath):
    """List all registered APIs (default action)."""
    if ctx.invoked_subcommand is None:
        config.set_config_path(jn)
        names = config.api_names()
        if not names:
            typer.echo("No APIs defined.")
            return
        for name in names:
            typer.echo(name)


@app.command()
def add(
    name: str = typer.Argument(..., help="Unique name for the API"),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="Base URL for REST API"),
    auth_type: Optional[str] = typer.Option(None, "--auth", help="Auth type: bearer, basic, oauth2, api_key"),
    token: Optional[str] = typer.Option(None, "--token", help="Auth token (supports ${env:VAR})"),
    username: Optional[str] = typer.Option(None, "--username", help="Username for basic auth or DB user"),
    password: Optional[str] = typer.Option(None, "--password", help="Password (supports ${env:VAR})"),
    header: Optional[List[str]] = typer.Option(None, "--header", help="HTTP header in KEY:VALUE format"),
    source_method: str = typer.Option("GET", "--source-method", help="Default HTTP method when used as source"),
    target_method: str = typer.Option("POST", "--target-method", help="Default HTTP method when used as target"),
    api_type: str = typer.Option("rest", "--type", help="API type: rest, graphql, postgres, mysql, s3, gcs, kafka"),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Add a new API configuration.

    Examples:
      jn api add github --base-url https://api.github.com --auth bearer --token '${env:GITHUB_TOKEN}'
      jn api add mydb --type postgres --host localhost --username admin --password '${env:DB_PASSWORD}'
    """
    config.set_config_path(jn)

    # Parse headers
    headers = {}
    if header:
        for h in header:
            if ":" not in h:
                typer.echo(f"Error: Invalid header format: {h}. Expected KEY:VALUE", err=True)
                raise typer.Exit(1)
            key, value = h.split(":", 1)
            headers[key.strip()] = value.strip()

    # Check if API already exists
    existing = config.get_api(name)
    if existing:
        typer.echo(f"API '{name}' already exists.", err=True)
        typer.echo()
        typer.echo("BEFORE:")
        typer.echo(json.dumps(existing.model_dump(exclude_none=True), indent=2))
        typer.echo()

        # Build new API config for preview
        from jn.models import Api, AuthConfig

        auth = None
        if auth_type:
            auth = AuthConfig(
                type=auth_type,  # type: ignore
                token=token,
                username=username,
                password=password,
            )

        new_api = Api(
            name=name,
            type=api_type,  # type: ignore
            base_url=base_url,
            auth=auth,
            headers=headers or {},
            source_method=source_method,
            target_method=target_method,
        )

        typer.echo("AFTER:")
        typer.echo(json.dumps(new_api.model_dump(exclude_none=True), indent=2))
        typer.echo()

        confirm = typer.confirm("Replace existing API?")
        if not confirm:
            typer.echo("Cancelled.")
            raise typer.Exit(0)

        # Remove existing before adding new
        cfg = config.require().model_copy(deep=True)
        cfg.apis = [a for a in cfg.apis if a.name != name]
        config.persist(cfg)

    result = config.add_api(
        name=name,
        api_type=api_type,  # type: ignore
        base_url=base_url,
        auth_type=auth_type,  # type: ignore
        token=token,
        username=username,
        password=password,
        headers=headers if headers else None,
        source_method=source_method,
        target_method=target_method,
    )

    if isinstance(result, Error):
        typer.echo(f"Error: {result.message}", err=True)
        raise typer.Exit(1)

    if existing:
        typer.echo(f"Replaced API: {name}")
    else:
        typer.echo(f"Created API: {name}")
    typer.echo(f"  Type: {result.type}")
    if result.base_url:
        typer.echo(f"  Base URL: {result.base_url}")
    if result.auth:
        typer.echo(f"  Auth: {result.auth.type}")


@app.command()
def show(
    name: str = typer.Argument(..., help="API name to display"),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Display details of a registered API.

    Example:
      jn api show github
    """
    config.set_config_path(jn)

    api = config.get_api(name)
    if not api:
        typer.echo(f"Error: API '{name}' not found", err=True)
        raise typer.Exit(1)

    api_dict = api.model_dump(exclude_none=True)
    typer.echo(json.dumps(api_dict, indent=2))


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
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Remove an API from the registry.

    Example:
      jn api rm github
      jn api rm github --force
    """
    config.set_config_path(jn)

    if not config.has_api(name):
        typer.echo(f"Error: API '{name}' not found", err=True)
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Remove API '{name}'?")
        if not confirm:
            typer.echo("Cancelled.")
            raise typer.Exit(0)

    # Load config, remove API, persist
    cfg = config.require().model_copy(deep=True)
    cfg.apis = [a for a in cfg.apis if a.name != name]
    config.persist(cfg)

    typer.echo(f"Removed API: {name}")
