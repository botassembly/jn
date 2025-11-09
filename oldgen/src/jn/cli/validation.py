"""Input validation helpers for CLI commands."""

from typing import Literal

import typer

# Type aliases for validated inputs
AuthType = Literal["bearer", "basic", "oauth2", "api_key"]
ApiType = Literal["rest", "graphql", "postgres", "mysql", "s3", "gcs", "kafka"]


def validate_auth_type(auth_type: str) -> AuthType:
    """Validate authentication type.

    Args:
        auth_type: Authentication type string

    Returns:
        Validated auth type

    Raises:
        typer.Exit: If auth type is invalid
    """
    valid_types: tuple[AuthType, ...] = (
        "bearer",
        "basic",
        "oauth2",
        "api_key",
    )
    if auth_type not in valid_types:
        typer.echo(
            f"Error: Invalid auth type '{auth_type}'. "
            f"Must be one of: {', '.join(valid_types)}",
            err=True,
        )
        raise typer.Exit(1)
    return auth_type  # type: ignore[return-value]


def validate_api_type(api_type: str) -> ApiType:
    """Validate API type.

    Args:
        api_type: API type string

    Returns:
        Validated API type

    Raises:
        typer.Exit: If API type is invalid
    """
    valid_types: tuple[ApiType, ...] = (
        "rest",
        "graphql",
        "postgres",
        "mysql",
        "s3",
        "gcs",
        "kafka",
    )
    if api_type not in valid_types:
        typer.echo(
            f"Error: Invalid API type '{api_type}'. "
            f"Must be one of: {', '.join(valid_types)}",
            err=True,
        )
        raise typer.Exit(1)
    return api_type  # type: ignore[return-value]


def parse_headers(header_list: list[str]) -> dict[str, str]:
    """Parse header options in KEY:VALUE format.

    Args:
        header_list: List of header strings in KEY:VALUE format

    Returns:
        Dictionary of headers

    Raises:
        typer.Exit: If header format is invalid
    """
    headers = {}
    for h in header_list:
        if ":" not in h:
            typer.echo(
                f"Error: Invalid header format: {h}. Expected KEY:VALUE",
                err=True,
            )
            raise typer.Exit(1)
        key, value = h.split(":", 1)
        headers[key.strip()] = value.strip()
    return headers
