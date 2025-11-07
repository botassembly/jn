"""Real-world integration tests for jc adapter with actual jc binary.

These tests require `jc` to be installed. They demonstrate real-world usage
of the jc adapter with actual shell commands.
"""

import json
import shutil

import pytest

from jn.cli import app
from tests.helpers import (
    add_converter,
    add_exec_target,
    add_pipeline,
    init_config,
)


@pytest.mark.skipif(shutil.which("jc") is None, reason="jc not installed")
def test_jc_with_date_command(runner, tmp_path):
    """Real-world test: Parse 'date' command output with jc."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create exec source with jc adapter for date command
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "exec",
                "current_date",
                "--adapter",
                "jc",
                "--argv",
                "date",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create converter to extract just the year
        result = runner.invoke(
            app,
            [
                "new",
                "converter",
                "extract_year",
                "--expr",
                ".year",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create target
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "exec",
                "cat",
                "--argv",
                "cat",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "get_year",
            ["source:current_date", "converter:extract_year", "target:cat"],
        )

        # Run the pipeline
        result = runner.invoke(app, ["run", "get_year", "--jn", str(jn_path)])

    assert result.exit_code == 0, f"Pipeline failed: {result.output}"
    output = result.output.strip()
    year = int(output)
    assert 2020 <= year <= 2030  # Sanity check


@pytest.mark.skipif(shutil.which("jc") is None, reason="jc not installed")
def test_jc_with_env_command(runner, tmp_path):
    """Real-world test: Parse 'env' command output and filter."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create source that lists environment variables
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "exec",
                "list_env",
                "--adapter",
                "jc",
                "--argv",
                "env",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create converter to filter and extract PATH variable
        result = runner.invoke(
            app,
            [
                "new",
                "converter",
                "get_path",
                "--expr",
                '.[] | select(.name == "PATH") | .value',
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create target
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "exec",
                "cat",
                "--argv",
                "cat",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "show_path",
            ["source:list_env", "converter:get_path", "target:cat"],
        )

        # Run the pipeline
        result = runner.invoke(app, ["run", "show_path", "--jn", str(jn_path)])

    assert result.exit_code == 0, f"Pipeline failed: {result.output}"
    output = result.output.strip()
    # PATH should contain at least /usr/bin or similar
    assert "/" in output
    assert len(output) > 10


@pytest.mark.skip(
    reason="jc magic mode only works with registered commands, not arbitrary scripts"
)
def test_jc_with_custom_command_and_filtering(runner, tmp_path):
    """Real-world test: Complex pipeline with multiple transformations."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create a Python script that outputs CSV-like data
        script = tmp_path / "generate_users.py"
        script.write_text(
            """#!/usr/bin/env python3
print("name,age,city")
print("Alice,30,NYC")
print("Bob,25,LA")
print("Charlie,35,Chicago")
print("Diana,28,NYC")
"""
        )
        script.chmod(0o755)

        # Create source with jc adapter to parse the CSV output
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "exec",
                "users",
                "--adapter",
                "jc",
                "--argv",
                str(script),
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create converter to filter users from NYC who are over 25
        result = runner.invoke(
            app,
            [
                "new",
                "converter",
                "filter_nyc",
                "--expr",
                '.[] | select(.city == "NYC" and (.age | tonumber) > 25)',
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create target
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "exec",
                "cat",
                "--argv",
                "cat",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "nyc_users",
            ["source:users", "converter:filter_nyc", "target:cat"],
        )

        # Run the pipeline
        result = runner.invoke(app, ["run", "nyc_users", "--jn", str(jn_path)])

    assert result.exit_code == 0, f"Pipeline failed: {result.output}"

    # Parse the output - should be NDJSON with filtered results
    lines = [line for line in result.output.strip().split("\n") if line]

    # Should have at least one result (Alice or Diana from NYC)
    assert len(lines) >= 1

    # Each line should be valid JSON
    for line in lines:
        data = json.loads(line)
        assert data["city"] == "NYC"
        assert int(data["age"]) > 25


def test_jc_adapter_configuration_persists(runner, tmp_path):
    """Test that adapter configuration is properly saved and loaded."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create source with jc adapter
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "exec",
                "test_source",
                "--adapter",
                "jc",
                "--argv",
                "echo",
                "--argv",
                "test",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Read the config file
        config_text = jn_path.read_text()
        config_data = json.loads(config_text)

    # Verify the adapter field is present and correct
    assert "sources" in config_data
    assert len(config_data["sources"]) == 1
    source = config_data["sources"][0]
    assert source["name"] == "test_source"
    assert source["driver"] == "exec"
    assert source["adapter"] == "jc"
    assert source["exec"]["argv"] == ["echo", "test"]


@pytest.mark.skipif(shutil.which("jc") is None, reason="jc not installed")
def test_jc_explain_shows_adapter(runner, tmp_path):
    """Test that 'jn explain' shows the adapter in the plan."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create source with jc adapter
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "exec",
                "date_source",
                "--adapter",
                "jc",
                "--argv",
                "date",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create converter
        result = runner.invoke(
            app,
            [
                "new",
                "converter",
                "pass",
                "--expr",
                ".",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create target
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "exec",
                "cat",
                "--argv",
                "cat",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "test_pipeline",
            ["source:date_source", "converter:pass", "target:cat"],
        )

        # Explain the pipeline
        result = runner.invoke(
            app, ["explain", "test_pipeline", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    # The output should show the pipeline structure
    assert "date_source" in result.output
    assert "pass" in result.output
    assert "cat" in result.output
