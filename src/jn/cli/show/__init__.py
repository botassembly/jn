"""CLI commands: jn show - display item definitions.

Simplified for apis and filters architecture.
"""

import typer

from .. import app as main_app  # noqa: E402

# Create the show command group first
show_app = typer.Typer(help="Show item definitions")

# Import command functions
from .api import show_api  # noqa: E402
from .filter import show_filter  # noqa: E402

# Register commands directly
show_app.command(name="api")(show_api)
show_app.command(name="filter")(show_filter)

# Register the show command group with the main app
main_app.add_typer(show_app, name="show")
