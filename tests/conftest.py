import json
from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    """Typer CliRunner instance."""
    return CliRunner()


@pytest.fixture
def tmp_config(tmp_path):
    """Create a temporary config directory with standard layout."""
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "out"
    data_dir.mkdir()
    out_dir.mkdir()
    return tmp_path


@pytest.fixture
def format_test_config(tmp_path):
    """Setup comprehensive test config for format adapter tests.

    Returns path to jn.json with all test pipelines configured.
    Creates test data files as needed.
    """
    # Load the comprehensive test config fixture
    fixture_path = Path(__file__).parent / "fixtures" / "test_config.json"
    config = json.loads(fixture_path.read_text())

    # Create data directory with test CSV
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    csv_file = data_dir / "input.csv"
    csv_file.write_text(
        "name,age,city\n"
        "Alice,30,NYC\n"
        "Bob,25,SF\n"
    )

    # Write config to tmp_path
    config_file = tmp_path / "jn.json"
    config_file.write_text(json.dumps(config, indent=2))

    return config_file
