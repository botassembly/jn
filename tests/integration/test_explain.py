"""End-to-end tests for jn explain command."""

import json

from jn.cli import app
from tests.helpers import (
    add_converter,
    add_exec_source,
    add_exec_target,
    add_pipeline,
    init_config,
)


def test_explain_basic_pipeline(
    runner, tmp_path, echo_source, pass_converter, cat_target
):
    """Test that jn explain shows pipeline structure."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        add_exec_source(runner, jn_path, "echo", echo_source.exec.argv)
        add_converter(runner, jn_path, "pass", pass_converter.jq.expr or ".")
        add_exec_target(runner, jn_path, "cat", cat_target.exec.argv)
        add_pipeline(
            runner,
            jn_path,
            "echo_to_cat",
            ["source:echo", "converter:pass", "target:cat"],
        )
        result = runner.invoke(
            app, ["explain", "echo_to_cat", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    output_data = json.loads(result.output)
    assert output_data["pipeline"] == "echo_to_cat"
    assert len(output_data["steps"]) == 3
    assert output_data["steps"][0]["type"] == "source"
    assert output_data["steps"][0]["name"] == "echo"
    assert output_data["steps"][1]["type"] == "converter"
    assert output_data["steps"][1]["name"] == "pass"
    assert output_data["steps"][2]["type"] == "target"
    assert output_data["steps"][2]["name"] == "cat"


def test_explain_with_show_commands(
    runner, tmp_path, echo_source, pass_converter, cat_target
):
    """Test that jn explain --show-commands displays command details."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        add_exec_source(runner, jn_path, "echo", echo_source.exec.argv)
        add_converter(runner, jn_path, "pass", pass_converter.jq.expr or ".")
        add_exec_target(runner, jn_path, "cat", cat_target.exec.argv)
        add_pipeline(
            runner,
            jn_path,
            "echo_to_cat",
            ["source:echo", "converter:pass", "target:cat"],
        )
        result = runner.invoke(
            app,
            [
                "explain",
                "echo_to_cat",
                "--show-commands",
                "--jn",
                str(jn_path),
            ],
        )

    assert result.exit_code == 0
    output_data = json.loads(result.output)
    assert "steps" in output_data
    # Check that source step has command info
    source_step = output_data["steps"][0]
    assert "argv" in source_step or "cmd" in source_step
    # Check that converter step has jq info
    converter_step = output_data["steps"][1]
    assert "expr" in converter_step or "jq" in converter_step


def test_explain_with_show_env(
    runner, tmp_path, echo_source, pass_converter, cat_target
):
    """Test that jn explain --show-env displays environment variables."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        add_exec_source(runner, jn_path, "echo", echo_source.exec.argv)
        add_converter(runner, jn_path, "pass", pass_converter.jq.expr or ".")
        add_exec_target(runner, jn_path, "cat", cat_target.exec.argv)
        add_pipeline(
            runner,
            jn_path,
            "echo_to_cat",
            ["source:echo", "converter:pass", "target:cat"],
        )
        result = runner.invoke(
            app, ["explain", "echo_to_cat", "--show-env", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    output_data = json.loads(result.output)
    assert "steps" in output_data
    # When --show-env is used, output should include step info
    assert len(output_data["steps"]) == 3


def test_explain_nonexistent_pipeline(runner, tmp_path):
    """Test error handling for nonexistent pipeline."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        result = runner.invoke(
            app, ["explain", "nonexistent", "--jn", str(jn_path)]
        )

    assert result.exit_code == 1
    assert result.exception is not None
    assert "not found" in str(result.exception)
