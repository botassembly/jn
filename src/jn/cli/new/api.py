"""CLI command: jn new api"""

from typing import List, Optional

import typer

from jn import config
from jn.models import Error
from jn.options import ConfigPath, ConfigPathType


def new_api(
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
    """Create a new API configuration.

    APIs are generic configurations that can be used as both sources and targets.

    Examples:

      # REST API with bearer auth
      jn new api github --base-url https://api.github.com --auth bearer --token '${env:GITHUB_TOKEN}'

      # GraphQL API
      jn new api github-gql --type graphql --endpoint https://api.github.com/graphql --auth bearer --token '${env:GITHUB_TOKEN}'

      # Add custom headers
      jn new api myapi --base-url https://api.example.com --header 'X-API-Key:${env:API_KEY}'
    """

    config.set_config_path(jn)

    # Parse headers if provided
    headers = {}
    if header:
        for h in header:
            if ":" not in h:
                typer.echo(f"Error: Invalid header format: {h}. Expected KEY:VALUE", err=True)
                raise typer.Exit(1)
            key, value = h.split(":", 1)
            headers[key.strip()] = value.strip()

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

    typer.echo(f"Created API: {name}")
    typer.echo(f"  Type: {result.type}")
    if result.base_url:
        typer.echo(f"  Base URL: {result.base_url}")
    if result.auth:
        typer.echo(f"  Auth: {result.auth.type}")
