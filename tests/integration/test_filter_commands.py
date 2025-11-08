"""Tests for jn filter commands (add, show, rm, list)."""

import json

from jn.cli import app
from tests.helpers import add_filter, init_config


def test_filter_add_creates_new_filter(runner, tmp_path):
    """Test that jn filter add creates a new filter."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)

    result = runner.invoke(
        app,
        [
            "filter",
            "add",
            "high-value",
            "--query",
            "select(.amount > 1000)",
            "--description",
            "Filter high value items",
            "--jn",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "Created filter: high-value" in result.output

    # Verify config was updated
    config = json.loads(config_path.read_text())
    assert len(config["filters"]) == 1
    assert config["filters"][0]["name"] == "high-value"
    assert config["filters"][0]["query"] == "select(.amount > 1000)"
    assert config["filters"][0]["description"] == "Filter high value items"


def test_filter_list_shows_filters(runner, tmp_path):
    """Test that jn filter lists all filters."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)
    add_filter(runner, config_path, "filter1", ".")
    add_filter(runner, config_path, "filter2", "select(.x)")

    result = runner.invoke(app, ["filter", "--jn", str(config_path)])

    assert result.exit_code == 0
    assert "filter1" in result.output
    assert "filter2" in result.output


def test_filter_show_displays_details(runner, tmp_path):
    """Test that jn filter show displays filter details."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)
    add_filter(runner, config_path, "test", "select(.amount > 100)")

    result = runner.invoke(app, ["filter", "show", "test", "--jn", str(config_path)])

    assert result.exit_code == 0
    output_json = json.loads(result.output)
    assert output_json["name"] == "test"
    assert output_json["query"] == "select(.amount > 100)"


def test_filter_rm_removes_filter(runner, tmp_path):
    """Test that jn filter rm removes a filter."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)
    add_filter(runner, config_path, "test", ".")

    # Verify filter exists
    config = json.loads(config_path.read_text())
    assert len(config["filters"]) == 1

    # Remove with --force to skip confirmation
    result = runner.invoke(app, ["filter", "rm", "test", "--force", "--jn", str(config_path)])

    assert result.exit_code == 0
    assert "Removed filter: test" in result.output

    # Verify filter was removed
    config = json.loads(config_path.read_text())
    assert len(config["filters"]) == 0


def test_filter_add_with_yes_flag_replaces_without_prompt(runner, tmp_path):
    """Test that --yes flag replaces existing filter without prompting."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)
    add_filter(runner, config_path, "test", ".")

    # Replace with different query using --yes
    result = runner.invoke(
        app,
        [
            "filter",
            "add",
            "test",
            "--query",
            "select(.x)",
            "--yes",
            "--jn",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "Replaced filter: test" in result.output

    # Verify it was replaced
    config = json.loads(config_path.read_text())
    assert config["filters"][0]["query"] == "select(.x)"


def test_filter_add_with_skip_if_exists(runner, tmp_path):
    """Test that --skip-if-exists skips adding if filter exists."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)
    add_filter(runner, config_path, "test", ".")

    # Try to add again with --skip-if-exists
    result = runner.invoke(
        app,
        [
            "filter",
            "add",
            "test",
            "--query",
            "select(.x)",
            "--skip-if-exists",
            "--jn",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "already exists, skipping" in result.output

    # Verify original wasn't changed
    config = json.loads(config_path.read_text())
    assert config["filters"][0]["query"] == "."


def test_filter_show_nonexistent_returns_error(runner, tmp_path):
    """Test that showing nonexistent filter returns error."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)

    result = runner.invoke(app, ["filter", "show", "nonexistent", "--jn", str(config_path)])

    assert result.exit_code == 1
    assert "not found" in result.output


def test_filter_rm_nonexistent_returns_error(runner, tmp_path):
    """Test that removing nonexistent filter returns error."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)

    result = runner.invoke(app, ["filter", "rm", "nonexistent", "--force", "--jn", str(config_path)])

    assert result.exit_code == 1
    assert "not found" in result.output
