"""Tests for jn api commands (add, show, rm, list)."""

import json

from jn.cli import app
from tests.helpers import add_api, init_config


def test_api_add_creates_new_api(runner, tmp_path):
    """Test that jn api add creates a new API."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)

    result = runner.invoke(
        app,
        [
            "api",
            "add",
            "github",
            "--base-url",
            "https://api.github.com",
            "--auth",
            "bearer",
            "--token",
            "${env:GITHUB_TOKEN}",
            "--jn",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "Created API: github" in result.output

    # Verify config was updated
    config = json.loads(config_path.read_text())
    assert len(config["apis"]) == 1
    assert config["apis"][0]["name"] == "github"
    assert config["apis"][0]["base_url"] == "https://api.github.com"
    assert config["apis"][0]["auth"]["type"] == "bearer"
    assert config["apis"][0]["auth"]["token"] == "${env:GITHUB_TOKEN}"


def test_api_list_shows_apis(runner, tmp_path):
    """Test that jn api lists all APIs."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)
    add_api(runner, config_path, "github", "https://api.github.com")
    add_api(runner, config_path, "gitlab", "https://gitlab.com/api")

    result = runner.invoke(app, ["api", "--jn", str(config_path)])

    assert result.exit_code == 0
    assert "github" in result.output
    assert "gitlab" in result.output


def test_api_show_displays_details(runner, tmp_path):
    """Test that jn api show displays API details."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)
    add_api(runner, config_path, "github", "https://api.github.com", "bearer", "${env:TOKEN}")

    result = runner.invoke(app, ["api", "show", "github", "--jn", str(config_path)])

    assert result.exit_code == 0
    output_json = json.loads(result.output)
    assert output_json["name"] == "github"
    assert output_json["base_url"] == "https://api.github.com"
    assert output_json["auth"]["type"] == "bearer"


def test_api_rm_removes_api(runner, tmp_path):
    """Test that jn api rm removes an API."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)
    add_api(runner, config_path, "github", "https://api.github.com")

    # Verify API exists
    config = json.loads(config_path.read_text())
    assert len(config["apis"]) == 1

    # Remove with --force to skip confirmation
    result = runner.invoke(app, ["api", "rm", "github", "--force", "--jn", str(config_path)])

    assert result.exit_code == 0
    assert "Removed API: github" in result.output

    # Verify API was removed
    config = json.loads(config_path.read_text())
    assert len(config["apis"]) == 0


def test_api_add_with_yes_flag_replaces_without_prompt(runner, tmp_path):
    """Test that --yes flag replaces existing API without prompting."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)
    add_api(runner, config_path, "test", "https://test.com")

    # Replace with different URL using --yes
    result = runner.invoke(
        app,
        [
            "api",
            "add",
            "test",
            "--base-url",
            "https://test2.com",
            "--yes",
            "--jn",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "Replaced API: test" in result.output

    # Verify it was replaced
    config = json.loads(config_path.read_text())
    assert config["apis"][0]["base_url"] == "https://test2.com"


def test_api_add_with_skip_if_exists(runner, tmp_path):
    """Test that --skip-if-exists skips adding if API exists."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)
    add_api(runner, config_path, "test", "https://test.com")

    # Try to add again with --skip-if-exists
    result = runner.invoke(
        app,
        [
            "api",
            "add",
            "test",
            "--base-url",
            "https://test2.com",
            "--skip-if-exists",
            "--jn",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "already exists, skipping" in result.output

    # Verify original wasn't changed
    config = json.loads(config_path.read_text())
    assert config["apis"][0]["base_url"] == "https://test.com"


def test_api_show_nonexistent_returns_error(runner, tmp_path):
    """Test that showing nonexistent API returns error."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)

    result = runner.invoke(app, ["api", "show", "nonexistent", "--jn", str(config_path)])

    assert result.exit_code == 1
    assert "not found" in result.output


def test_api_rm_nonexistent_returns_error(runner, tmp_path):
    """Test that removing nonexistent API returns error."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)

    result = runner.invoke(app, ["api", "rm", "nonexistent", "--force", "--jn", str(config_path)])

    assert result.exit_code == 1
    assert "not found" in result.output
