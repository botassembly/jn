"""Shared CLI option definitions."""

from pathlib import Path

import typer

ConfigPathType = Path | None

ConfigPath = typer.Option(
    None,
    "--jn",
    help="Path to jn.json config file",
)

__all__ = ["ConfigPath", "ConfigPathType"]
