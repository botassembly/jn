"""CLI layer: Typer command registration and app wiring."""

import typer

app = typer.Typer(
    name="jn",
    help="JN (Junction): Source → jq → Target streaming pipelines",
    no_args_is_help=True,
)

# Register commands
from . import init as init_cmd
from . import list as list_cmd
from . import run as run_cmd

init_cmd.register(app)
list_cmd.register(app)
run_cmd.register(app)


def main() -> None:
    """Entry point for the jn CLI."""
    app()
