"""CLI layer: Typer command registration and app wiring."""

import typer

from jn.options import ConfigPath

app = typer.Typer(
    name="jn",
    help="JN (Junction): Source → jq → Target streaming pipelines",
    no_args_is_help=True,
)

__all__ = ["ConfigPath", "app"]

# Import commands to register decorators
from . import explain, init, list, new, run, show  # noqa: F401
