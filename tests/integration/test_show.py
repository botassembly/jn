"""End-to-end tests for jn show command."""

import json

import pytest

from jn.cli import app
from tests.helpers import (
    add_converter,
    add_exec_source,
    add_exec_target,
    add_pipeline,
    init_config,
)


def test_show_source(runner, tmp_path, echo_source):
    """Test that jn show source displays source JSON."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        add_exec_source(runner, jn_path, "echo", echo_source.exec.argv)
        result = runner.invoke(
            app, ["show", "source", "echo", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    output_data = json.loads(result.output)
    assert output_data["name"] == "echo"
    assert output_data["driver"] == "exec"


def test_show_target(runner, tmp_path, cat_target):
    """Test that jn show target displays target JSON."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        add_exec_target(runner, jn_path, "cat", cat_target.exec.argv)
        result = runner.invoke(
            app, ["show", "target", "cat", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    output_data = json.loads(result.output)
    assert output_data["name"] == "cat"
    assert output_data["driver"] == "exec"


def test_show_converter(runner, tmp_path, pass_converter):
    """Test that jn show converter displays converter JSON."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        add_converter(runner, jn_path, "pass", pass_converter.jq.expr or ".")
        result = runner.invoke(
            app, ["show", "converter", "pass", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    output_data = json.loads(result.output)
    assert output_data["name"] == "pass"
    assert output_data["engine"] == "jq"


def test_show_pipeline(
    runner, tmp_path, echo_source, pass_converter, cat_target
):
    """Test that jn show pipeline displays pipeline JSON."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        add_exec_source(runner, jn_path, "echo", echo_source.exec.argv)
        add_converter(runner, jn_path, "pass", pass_converter.jq.expr or ".")
        add_exec_target(runner, jn_path, "cat", cat_target.exec.argv)
        add_pipeline(
            runner,
            jn_path,
            "test_pipeline",
            ["source:echo", "converter:pass", "target:cat"],
        )
        result = runner.invoke(
            app, ["show", "pipeline", "test_pipeline", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    output_data = json.loads(result.output)
    assert output_data["name"] == "test_pipeline"
    assert len(output_data["steps"]) == 3


@pytest.mark.parametrize(
    ("entity", "name", "expected"),
    (
        (
            "source",
            "missing-source",
            "Error: source 'missing-source' not found",
        ),
        (
            "target",
            "missing-target",
            "Error: target 'missing-target' not found",
        ),
        (
            "converter",
            "missing-converter",
            "Error: converter 'missing-converter' not found",
        ),
        (
            "pipeline",
            "missing-pipeline",
            "Error: pipeline 'missing-pipeline' not found",
        ),
    ),
)
def test_show_nonexistent_item(runner, tmp_path, entity, name, expected):
    """Test error handling for nonexistent items across show subcommands."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        result = runner.invoke(
            app,
            ["show", entity, name, "--jn", str(jn_path)],
        )

    assert result.exit_code == 1
    assert expected in result.output
