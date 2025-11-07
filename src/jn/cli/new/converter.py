"""CLI command: jn new converter - create converters."""

import typer

from jn import ConfigPath, ConfigPathType, config

from . import new_app


@new_app.command()
def converter(
    name: str,
    jn: ConfigPathType = ConfigPath,
    expr: str | None = typer.Option(
        None,
        "--expr",
        help="jq expression (inline)",
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help="Path to jq filter file",
    ),
    raw: bool = typer.Option(
        False,
        "--raw",
        help="Output raw strings",
    ),
    modules: str | None = typer.Option(
        None,
        "--modules",
        help="Path to jq modules directory",
    ),
) -> None:
    """Create a new jq converter."""
    config.set_config_path(jn)

    result = config.add_converter(
        name,
        expr=expr,
        file=file,
        raw=raw,
        modules=modules,
    )

    if isinstance(result, config.Error):
        typer.echo(str(result), err=True)
        raise typer.Exit(1)

    typer.echo(f"Created converter '{result.name}'")
