"""CLI command: jn new converter - create converters."""

from pathlib import Path
from typing import Optional

import typer

from ...config import get_config
from ...service.new import add_converter
from . import new_app


@new_app.command()
def converter(
    name: str,
    expr: Optional[str] = typer.Option(
        None,
        "--expr",
        help="jq expression (inline)",
    ),
    file: Optional[str] = typer.Option(
        None,
        "--file",
        help="Path to jq filter file",
    ),
    raw: bool = typer.Option(
        False,
        "--raw",
        help="Output raw strings",
    ),
    modules: Optional[str] = typer.Option(
        None,
        "--modules",
        help="Path to jq modules directory",
    ),
    jn: Optional[Path] = typer.Option(
        None,
        help="Path to jn.json config file",
    ),
) -> None:
    """Create a new jq converter."""
    config = get_config(jn)

    add_converter(
        config=config,
        jn_path=jn,
        name=name,
        expr=expr,
        file=file,
        raw=raw,
        modules=modules,
    )

    typer.echo(f"Created converter '{name}'")
