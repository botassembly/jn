"""End-to-end tests for jn init command."""

import json

from jn.cli import app


def test_init_creates_file(runner, tmp_path):
    """Test that jn init creates a jn.json file."""
    jn_path = tmp_path / "jn.json"

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["init", "--jn", str(jn_path)])

    assert result.exit_code == 0
    assert jn_path.exists()
    assert "Created" in result.output


def test_init_refuses_overwrite_without_force(runner, tmp_path):
    """Test that jn init refuses to overwrite existing file without --force."""
    jn_path = tmp_path / "jn.json"
    jn_path.write_text('{"test": "data"}')

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["init", "--jn", str(jn_path)])

    assert result.exit_code == 1
    assert "already exists" in result.output


def test_init_overwrites_with_force(runner, tmp_path):
    """Test that jn init overwrites with --force flag."""
    jn_path = tmp_path / "jn.json"
    jn_path.write_text('{"test": "data"}')

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["init", "--jn", str(jn_path), "--force"])

    assert result.exit_code == 0
    assert "Created" in result.output
    data = json.loads(jn_path.read_text())
    assert data["version"] == "0.1"
    assert "sources" in data
