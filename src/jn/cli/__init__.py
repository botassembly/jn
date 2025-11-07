"""CLI layer: Typer command registration and app wiring."""

import typer

app = typer.Typer(
    name="jn",
    help="JN (Junction): Source → jq → Target streaming pipelines",
    no_args_is_help=True,
)

# Import commands to register decorators
from . import init, list, run  # noqa: F401
