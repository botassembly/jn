"""End-to-end tests for jn new target command."""

import json

from jn.cli import app


def test_new_target_exec(runner, tmp_path):
    """Test creating a new exec target."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "test.cat",
                "exec",
                "--argv",
                "cat",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 0
    assert "Created target" in result.output or "test.cat" in result.output
    data = json.loads(jn_path.read_text())
    assert len(data["targets"]) == 1
    assert data["targets"][0]["name"] == "test.cat"
    assert data["targets"][0]["driver"] == "exec"
    assert data["targets"][0]["exec"]["argv"] == ["cat"]


def test_new_target_shell(runner, tmp_path):
    """Test creating a new shell target."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "test.shell",
                "shell",
                "--cmd",
                "tee output.json",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 0
    data = json.loads(jn_path.read_text())
    assert data["targets"][0]["name"] == "test.shell"
    assert data["targets"][0]["driver"] == "shell"
    assert data["targets"][0]["shell"]["cmd"] == "tee output.json"


def test_new_target_curl(runner, tmp_path):
    """Test creating a new curl target (defaults to POST)."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "test.api",
                "curl",
                "--url",
                "https://api.example.com/webhook",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 0
    data = json.loads(jn_path.read_text())
    assert data["targets"][0]["name"] == "test.api"
    assert data["targets"][0]["driver"] == "curl"
    assert (
        data["targets"][0]["curl"]["url"] == "https://api.example.com/webhook"
    )
    assert data["targets"][0]["curl"]["method"] == "POST"


def test_new_target_file(runner, tmp_path):
    """Test creating a new file target (write mode)."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "test.file",
                "file",
                "--path",
                "output/result.json",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 0
    data = json.loads(jn_path.read_text())
    assert data["targets"][0]["name"] == "test.file"
    assert data["targets"][0]["driver"] == "file"
    assert data["targets"][0]["file"]["path"] == "output/result.json"
    assert data["targets"][0]["file"]["mode"] == "write"


def test_new_target_duplicate_name(runner, tmp_path):
    """Test error handling for duplicate target names."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        runner.invoke(
            app,
            [
                "new",
                "target",
                "duplicate",
                "exec",
                "--argv",
                "cat",
                "--jn",
                str(jn_path),
            ],
        )
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "duplicate",
                "exec",
                "--argv",
                "tee",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 1
    assert (
        "already exists" in result.output
        or "duplicate" in result.output.lower()
    )
