"""Pytest fixtures and configuration for jn tests."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from jn.models.project import (
    Converter,
    ExecSpec,
    JqConfig,
    Pipeline,
    Project,
    Source,
    Step,
    Target,
)


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


@pytest.fixture
def echo_source():
    """Source that echoes two JSON objects."""
    return Source(
        name="echo",
        driver="exec",
        exec=ExecSpec(
            argv=[
                "python",
                "-c",
                "import json; print(json.dumps({'x': 1})); print(json.dumps({'x': 2}))",
            ]
        ),
    )


@pytest.fixture
def numbers_source():
    """Source that outputs numbers 1 and 2."""
    return Source(
        name="numbers",
        driver="exec",
        exec=ExecSpec(
            argv=[
                "python",
                "-c",
                "import json; print(json.dumps({'n': 1})); print(json.dumps({'n': 2}))",
            ]
        ),
    )


@pytest.fixture
def failing_source():
    """Source that fails immediately."""
    return Source(name="failing", driver="exec", exec=ExecSpec(argv=["false"]))


@pytest.fixture
def pass_converter():
    """Converter that passes through unchanged."""
    return Converter(name="pass", engine="jq", jq=JqConfig(expr="."))


@pytest.fixture
def double_converter():
    """Converter that doubles the 'n' field."""
    return Converter(
        name="double", engine="jq", jq=JqConfig(expr="{n: (.n * 2)}")
    )


@pytest.fixture
def cat_target():
    """Target that outputs to stdout via cat."""
    return Target(name="cat", driver="exec", exec=ExecSpec(argv=["cat"]))
