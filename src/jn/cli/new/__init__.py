"""CLI commands: jn new - create new config items."""

import typer

# Create the new command group first
new_app = typer.Typer(help="Create new config items")

# Import modules which will register their commands via decorators
from .. import app as main_app  # noqa: E402
from . import converter, pipeline, source, target  # noqa: E402, F401

# Register subcommand groups
new_app.add_typer(source.app, name="source")
new_app.add_typer(target.app, name="target")

# Register the new command group with the main app
main_app.add_typer(new_app, name="new")
