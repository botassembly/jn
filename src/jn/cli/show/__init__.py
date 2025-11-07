"""CLI commands: jn show - display item definitions."""

import typer

# Create the show command group first
show_app = typer.Typer(help="Show item definitions")

# Import modules which will register their commands via decorators
from .. import app as main_app  # noqa: E402
from . import converter, pipeline, source, target  # noqa: E402, F401

# Register the show command group with the main app
main_app.add_typer(show_app, name="show")
