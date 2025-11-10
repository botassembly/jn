"""Test JN CLI commands using Click test runner."""

import json
from pathlib import Path

import pytest

from jn.cli import cli


def test_plugin_call_csv_read(people_csv):
    """Test: Direct plugin invocation (csv read mode)."""
    import subprocess
    import sys

    # Find plugin directly
    plugin_path = (
        Path(__file__).parent.parent
        / "src"
        / "jn"
        / "plugins"
        / "formats"
        / "csv_.py"
    )

    with open(people_csv) as f:
        result = subprocess.run(
            [sys.executable, str(plugin_path), "--mode", "read"],
            stdin=f,
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) == 5

    first = json.loads(lines[0])
    assert first["name"] == "Alice"


def test_plugin_call_json_write(sample_ndjson):
    """Test: Direct plugin invocation (json write mode)."""
    import subprocess
    import sys

    # Find plugin directly
    plugin_path = (
        Path(__file__).parent.parent
        / "src"
        / "jn"
        / "plugins"
        / "formats"
        / "json_.py"
    )

    result = subprocess.run(
        [sys.executable, str(plugin_path), "--mode", "write"],
        input=sample_ndjson,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 2
    assert data[0]["name"] == "Alice"


def test_cat_csv_to_stdout(people_csv):
    """Test: jn cat file.csv (using real subprocess)."""
    import subprocess

    # Use real subprocess instead of CliRunner (which can't capture subprocess output)
    result = subprocess.run(
        ["uv", "run", "jn", "cat", str(people_csv)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) == 5


def test_cat_csv_to_json(cli_runner, people_csv, tmp_path):
    """Test: jn run file.csv file.json."""
    output_file = tmp_path / "output.json"

    result = cli_runner.invoke(cli, ["run", str(people_csv), str(output_file)])

    assert result.exit_code == 0
    assert output_file.exists()

    with open(output_file) as f:
        data = json.load(f)

    assert len(data) == 5
    assert data[0]["name"] == "Alice"


def test_cat_with_custom_home(people_csv, jn_home, tmp_path):
    """Test: jn --home custom/path run file.csv file.json (uses built-in plugin fallback)."""
    import subprocess

    output_file = tmp_path / "output.json"

    # Use real subprocess (CliRunner has issues with subprocess-based commands)
    result = subprocess.run(
        [
            "uv",
            "run",
            "jn",
            "--home",
            str(jn_home),
            "run",
            str(people_csv),
            str(output_file),
        ],
        capture_output=True,
        text=True,
    )

    # Should work with custom home (empty plugins dir falls back to built-in)
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    assert output_file.exists()

    # Verify output
    with open(output_file) as f:
        data = json.load(f)
    assert len(data) == 5
    assert data[0]["name"] == "Alice"


def test_head_command(cli_runner, sample_ndjson):
    """Test: jn head -n 1."""
    result = cli_runner.invoke(cli, ["head", "-n", "1"], input=sample_ndjson)

    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert len(lines) == 1
    assert json.loads(lines[0])["name"] == "Alice"


def test_tail_command(cli_runner, sample_ndjson):
    """Test: jn tail -n 1."""
    result = cli_runner.invoke(cli, ["tail", "-n", "1"], input=sample_ndjson)

    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert len(lines) == 1
    assert json.loads(lines[0])["name"] == "Bob"


def test_plugin_list(cli_runner):
    """Test: jn plugin list."""
    result = cli_runner.invoke(cli, ["plugin", "list"])

    assert result.exit_code == 0
    # Should list built-in plugins
    assert "csv_" in result.output
    assert "json_" in result.output
    assert "yaml_" in result.output


def test_run_command(cli_runner, people_csv, tmp_path):
    """Test: jn run input.csv output.json."""
    output_file = tmp_path / "output.json"

    result = cli_runner.invoke(cli, ["run", str(people_csv), str(output_file)])

    assert result.exit_code == 0
    assert output_file.exists()

    with open(output_file) as f:
        data = json.load(f)

    assert len(data) == 5
