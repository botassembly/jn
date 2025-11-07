"""CLI commands: jn new - create new project items."""

import typer

from .. import app as main_app
from . import converter, pipeline, source, target

new_app = typer.Typer(help="Create new project items")

# Register subcommand groups
new_app.add_typer(source.app, name="source")
new_app.add_typer(target.app, name="target")

# Register individual commands
new_app.command(name="converter")(converter.create_converter)
new_app.command(name="pipeline")(pipeline.create_pipeline)

# Register the new command group with the main app
main_app.add_typer(new_app, name="new")
