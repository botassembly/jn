"""CLI layer: Typer command registration and app wiring."""

from pathlib import Path
from typing import Annotated

import typer

ConfigPath = Annotated[
    Path | None,
    typer.Option(
        "--jn",
        help="Path to jn.json config file",
    ),
]

app = typer.Typer(
    name="jn",
    help="JN (Junction): Source → jq → Target streaming pipelines",
    no_args_is_help=True,
)

__all__ = ["ConfigPath", "app"]

# Import commands to register decorators
from . import explain, init, list, new, run, show  # noqa: F401
