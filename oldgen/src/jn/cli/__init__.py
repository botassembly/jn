"""CLI layer: Typer command registration and app wiring.

Simplified architecture with apis and filters.
Noun-first command structure: jn api, jn filter (like git).
"""

import typer

from jn.options import ConfigPath

app = typer.Typer(
    name="jn",
    help="JN (Junction): Data transformation with APIs and filters",
    no_args_is_help=True,
)

__all__ = ["ConfigPath", "app"]

# Import command modules
from . import api, cat, filter, init, put, run  # noqa: F401

# Register top-level command groups
app.add_typer(api.app, name="api")
app.add_typer(filter.app, name="filter")
