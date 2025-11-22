"""Pytest configuration and shared fixtures."""

import os
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from jn.cli import cli


@pytest.fixture(scope="session", autouse=True)
def setup_test_jn_home():
    """Set JN_HOME to tests/jn_home for all tests.

    This ensures tests use test fixture profiles (MCP profiles in tests/jn_home/profiles/mcp/)
    instead of the bundled ones in jn_home/.
    """
    test_jn_home = Path(__file__).parent / "jn_home"
    os.environ["JN_HOME"] = str(test_jn_home)

    # Clear the cached home path so it reads the new JN_HOME value
    import jn.context
    jn.context._cached_home = None

    yield
    # Cleanup: restore original JN_HOME if it existed
    # Note: The logic here was buggy - it always deletes if present
    # Should save/restore original value if it existed before
    if "JN_HOME" in os.environ:
        del os.environ["JN_HOME"]
    # Clear cache again after cleanup
    jn.context._cached_home = None


@pytest.fixture(autouse=True)
def clear_jn_cache():
    """Clear JN context cache before each test to prevent pollution.

    The _cached_home in jn.context persists across tests and can cause
    tests to use wrong JN_HOME values. This fixture ensures a clean state
    for each test.
    """
    import jn.context
    jn.context._cached_home = None
    yield
    # Clear again after test
    jn.context._cached_home = None


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
        if not hasattr(result, "output_bytes") and hasattr(
            result, "stdout_bytes"
        ):
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
