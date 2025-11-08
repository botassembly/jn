"""CLI commands: jn new - create new config items.

Simplified for apis and filters architecture.
"""

import typer

from .. import app as main_app  # noqa: E402

# Create the new command group first
new_app = typer.Typer(help="Create new config items")

# Import command functions
from .api import new_api  # noqa: E402
from .filter import new_filter  # noqa: E402

# Register commands directly
new_app.command(name="api")(new_api)
new_app.command(name="filter")(new_filter)

# Register the new command group with the main app
main_app.add_typer(new_app, name="new")
