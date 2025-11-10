"""Pytest configuration and shared fixtures."""

import tempfile
import pytest
from pathlib import Path
from click.testing import CliRunner


@pytest.fixture
def cli_runner():
    """Provide Click CLI test runner."""
    return CliRunner()


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
    return Path(__file__).parent / 'data'


@pytest.fixture
def people_csv(test_data):
    """Provide path to people.csv test file."""
    return test_data / 'people.csv'


@pytest.fixture
def sample_ndjson():
    """Provide sample NDJSON data as string."""
    return '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'
