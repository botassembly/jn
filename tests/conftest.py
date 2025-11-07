"""Pytest fixtures and configuration for jn tests."""

import pytest
from pathlib import Path
from typer.testing import CliRunner


@pytest.fixture
def runner():
    """Typer CliRunner instance."""
    return CliRunner()


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with standard layout."""
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "out"
    data_dir.mkdir()
    out_dir.mkdir()
    return tmp_path
