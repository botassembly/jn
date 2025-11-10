"""Test JN CLI commands using Click test runner."""

import json
from pathlib import Path

import pytest

from jn.cli import cli


@pytest.mark.skip(
    reason="Known Click issue: ignore_unknown_options doesn't work in nested groups via entry points. See docs/PLUGIN_CALL_RCA.md"
)
def test_plugin_call_csv_read(cli_runner, people_csv):
    """Test: jn plugin call csv_ --mode=read."""
    with open(people_csv) as f:
        result = cli_runner.invoke(
            cli, ["plugin", "call", "csv_", "--mode", "read"], input=f.read()
        )

    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 5

    first = json.loads(lines[0])
    assert first["name"] == "Alice"


@pytest.mark.skip(
    reason="Known Click issue: ignore_unknown_options doesn't work in nested groups via entry points. See docs/PLUGIN_CALL_RCA.md"
)
def test_plugin_call_json_write(cli_runner, sample_ndjson):
    """Test: jn plugin call json_ --mode=write."""
    result = cli_runner.invoke(
        cli,
        ["plugin", "call", "json_", "--mode", "write"],
        input=sample_ndjson,
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 2
    assert data[0]["name"] == "Alice"


@pytest.mark.skip(
    reason="CliRunner doesn't capture subprocess output from cat command"
)
def test_cat_csv_to_stdout(cli_runner, people_csv):
    """Test: jn cat file.csv."""
    result = cli_runner.invoke(cli, ["cat", str(people_csv)])

    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 5


def test_cat_csv_to_json(cli_runner, people_csv, tmp_path):
    """Test: jn cat file.csv file.json."""
    output_file = tmp_path / "output.json"

    result = cli_runner.invoke(cli, ["cat", str(people_csv), str(output_file)])

    assert result.exit_code == 0
    assert output_file.exists()

    with open(output_file) as f:
        data = json.load(f)

    assert len(data) == 5
    assert data[0]["name"] == "Alice"


@pytest.mark.skip(
    reason="Custom --home requires plugins in that directory. Need to implement plugin fallback or copy built-in plugins."
)
def test_cat_with_custom_home(cli_runner, people_csv, jn_home, tmp_path):
    """Test: jn --home custom/path cat file.csv."""
    output_file = tmp_path / "output.json"

    result = cli_runner.invoke(
        cli, ["--home", str(jn_home), "cat", str(people_csv), str(output_file)]
    )

    # Should work with custom home (uses built-in plugins)
    assert result.exit_code == 0
    assert output_file.exists()


def test_head_command(cli_runner, sample_ndjson):
    """Test: jn head 1."""
    result = cli_runner.invoke(cli, ["head", "1"], input=sample_ndjson)

    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert len(lines) == 1
    assert json.loads(lines[0])["name"] == "Alice"


def test_tail_command(cli_runner, sample_ndjson):
    """Test: jn tail 1."""
    result = cli_runner.invoke(cli, ["tail", "1"], input=sample_ndjson)

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
