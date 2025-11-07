"""End-to-end tests for jn new source command."""

import json

from jn.cli import app


def test_new_source_exec(runner, tmp_path):
    """Test creating a new exec source."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Initialize project first
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        # Create new source
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "test.echo",
                "exec",
                "--argv",
                "echo",
                "--argv",
                "hello",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 0
    assert "Created source" in result.output or "test.echo" in result.output
    # Verify the source was added to the file
    data = json.loads(jn_path.read_text())
    assert len(data["sources"]) == 1
    assert data["sources"][0]["name"] == "test.echo"
    assert data["sources"][0]["driver"] == "exec"
    assert data["sources"][0]["exec"]["argv"] == ["echo", "hello"]


def test_new_source_shell(runner, tmp_path):
    """Test creating a new shell source."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "test.shell",
                "shell",
                "--cmd",
                "echo hello | jq -c .",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 0
    data = json.loads(jn_path.read_text())
    assert len(data["sources"]) == 1
    assert data["sources"][0]["name"] == "test.shell"
    assert data["sources"][0]["driver"] == "shell"
    assert data["sources"][0]["shell"]["cmd"] == "echo hello | jq -c ."


def test_new_source_curl(runner, tmp_path):
    """Test creating a new curl source."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "test.api",
                "curl",
                "--url",
                "https://api.example.com/data",
                "--method",
                "GET",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 0
    data = json.loads(jn_path.read_text())
    assert len(data["sources"]) == 1
    assert data["sources"][0]["name"] == "test.api"
    assert data["sources"][0]["driver"] == "curl"
    assert data["sources"][0]["curl"]["url"] == "https://api.example.com/data"
    assert data["sources"][0]["curl"]["method"] == "GET"


def test_new_source_file(runner, tmp_path):
    """Test creating a new file source."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "test.file",
                "file",
                "--path",
                "data/input.json",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 0
    data = json.loads(jn_path.read_text())
    assert len(data["sources"]) == 1
    assert data["sources"][0]["name"] == "test.file"
    assert data["sources"][0]["driver"] == "file"
    assert data["sources"][0]["file"]["path"] == "data/input.json"
    assert data["sources"][0]["file"]["mode"] == "read"


def test_new_source_duplicate_name(runner, tmp_path):
    """Test error handling for duplicate source names."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        # Create first source
        runner.invoke(
            app,
            [
                "new",
                "source",
                "duplicate",
                "exec",
                "--argv",
                "echo",
                "--argv",
                "1",
                "--jn",
                str(jn_path),
            ],
        )
        # Try to create duplicate
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "duplicate",
                "exec",
                "--argv",
                "echo",
                "--argv",
                "2",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 1
    assert (
        "already exists" in result.output
        or "duplicate" in result.output.lower()
    )


def test_new_source_with_env(runner, tmp_path):
    """Test creating source with environment variables."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "test.env",
                "exec",
                "--argv",
                "env",
                "--env",
                "FOO=bar",
                "--env",
                "BAZ=qux",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 0
    data = json.loads(jn_path.read_text())
    assert data["sources"][0]["exec"]["env"]["FOO"] == "bar"
    assert data["sources"][0]["exec"]["env"]["BAZ"] == "qux"


def test_new_source_with_cwd(runner, tmp_path):
    """Test creating source with working directory."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "test.cwd",
                "exec",
                "--argv",
                "pwd",
                "--cwd",
                str(tmp_path),
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 0
    data = json.loads(jn_path.read_text())
    assert data["sources"][0]["exec"]["cwd"] == str(tmp_path)
