"""Pytest configuration and shared fixtures."""

import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from jn.cli import cli


@pytest.fixture
def cli_runner():
    """Provide Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def invoke(cli_runner):
    """Helper to invoke the CLI with args and optional input.

    Usage:
        result = invoke(["cat", "file.csv"])  # returns click.Result
        result = invoke(["run", "in.csv", "out.json"])  # exit_code, output, etc.
        result = invoke(["plugin", "call", "xlsx_", "--mode", "read"], input_data=bytes)

    Click's CliRunner automatically handles both text and binary input.
    Binary output can be accessed via result.output_bytes or result.stdout_bytes.
    """

    def _invoke(args, input_data=None):
        result = cli_runner.invoke(cli, args, input=input_data)
        # Ensure output_bytes is available for binary output access
        if not hasattr(result, 'output_bytes') and hasattr(result, 'stdout_bytes'):
            result.output_bytes = result.stdout_bytes
        return result

    return _invoke


@pytest.fixture
def jn_home(tmp_path):
    """Provide temporary JN_HOME directory with structure.

    Creates:
        tmp_path/plugins/     - Custom plugins
        tmp_path/profiles/    - Custom profiles
        tmp_path/cache.json   - Plugin cache
    """
    home = tmp_path / "jn_home"
    home.mkdir()

    # Create subdirectories
    (home / "plugins").mkdir()
    (home / "profiles").mkdir()

    return home


@pytest.fixture
def test_data():
    """Provide path to test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def people_csv(test_data):
    """Provide path to people.csv test file."""
    return test_data / "people.csv"


@pytest.fixture
def sample_ndjson():
    """Provide sample NDJSON data as string."""
    return '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'
