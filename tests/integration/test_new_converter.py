"""End-to-end tests for jn new converter command."""

import json

from jn.cli import app


def test_new_converter_with_expr(runner, tmp_path):
    """Test creating a converter with inline expression."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(
            app,
            [
                "new",
                "converter",
                "test.pass",
                "--expr",
                ".",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 0
    assert "Created converter" in result.output or "test.pass" in result.output
    data = json.loads(jn_path.read_text())
    assert len(data["converters"]) == 1
    assert data["converters"][0]["name"] == "test.pass"
    assert data["converters"][0]["engine"] == "jq"
    assert data["converters"][0]["jq"]["expr"] == "."


def test_new_converter_with_file(runner, tmp_path):
    """Test creating a converter with file reference."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(
            app,
            [
                "new",
                "converter",
                "test.transform",
                "--file",
                "filters/transform.jq",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 0
    data = json.loads(jn_path.read_text())
    assert data["converters"][0]["jq"]["file"] == "filters/transform.jq"


def test_new_converter_with_raw(runner, tmp_path):
    """Test creating a converter with raw output."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(
            app,
            [
                "new",
                "converter",
                "test.raw",
                "--expr",
                ".text",
                "--raw",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 0
    data = json.loads(jn_path.read_text())
    assert data["converters"][0]["jq"]["raw"] is True


def test_new_converter_with_modules(runner, tmp_path):
    """Test creating a converter with jq modules path."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(
            app,
            [
                "new",
                "converter",
                "test.modules",
                "--expr",
                ".",
                "--modules",
                "lib/jq",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 0
    data = json.loads(jn_path.read_text())
    assert data["converters"][0]["jq"]["modules"] == "lib/jq"


def test_new_converter_duplicate_name(runner, tmp_path):
    """Test error handling for duplicate converter names."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        runner.invoke(
            app,
            [
                "new",
                "converter",
                "duplicate",
                "--expr",
                ".",
                "--jn",
                str(jn_path),
            ],
        )
        result = runner.invoke(
            app,
            [
                "new",
                "converter",
                "duplicate",
                "--expr",
                ".x",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 1
    assert result.exception is not None
    assert "already exists" in (result.stderr or result.output)


def test_new_converter_requires_expr_or_file(runner, tmp_path):
    """Test that converter requires either --expr or --file."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(
            app,
            [
                "new",
                "converter",
                "test.missing",
                "--jn",
                str(jn_path),
            ],
        )
    assert result.exit_code == 1
    assert result.exception is not None
    error_text = (result.stderr or result.output).lower()
    assert "expr" in error_text or "file" in error_text
