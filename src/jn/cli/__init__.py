"""CLI layer: Typer command registration and app wiring.

Simplified architecture with apis and filters.
"""

import typer

from jn.options import ConfigPath

app = typer.Typer(
    name="jn",
    help="JN (Junction): Data transformation with APIs and filters",
    no_args_is_help=True,
)

__all__ = ["ConfigPath", "app"]

# Import commands to register decorators
from . import cat, init, list, new, put, run, show  # noqa: F401
