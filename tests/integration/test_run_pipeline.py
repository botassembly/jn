"""End-to-end tests for jn run command."""

import json

from jn.cli import app
from tests.helpers import (
    add_converter,
    add_exec_source,
    add_exec_target,
    add_pipeline,
    init_config,
)


def test_run_echo_pipeline(
    runner, tmp_path, echo_source, pass_converter, cat_target
):
    """Test running a simple echo pipeline."""

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
            app, ["run", "echo_to_cat", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"x": 1}
    assert json.loads(lines[1]) == {"x": 2}


def test_run_pipeline_with_jq_transform(
    runner, tmp_path, numbers_source, double_converter, cat_target
):
    """Test running a pipeline with jq transformation."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        add_exec_source(
            runner,
            jn_path,
            "numbers",
            numbers_source.exec.argv,
        )
        add_converter(
            runner,
            jn_path,
            "double",
            double_converter.jq.expr or ".",
        )
        add_exec_target(runner, jn_path, "cat", cat_target.exec.argv)
        add_pipeline(
            runner,
            jn_path,
            "double_numbers",
            ["source:numbers", "converter:double", "target:cat"],
        )

        result = runner.invoke(
            app, ["run", "double_numbers", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line]
    assert json.loads(lines[0]) == {"n": 2}
    assert json.loads(lines[1]) == {"n": 4}


def test_run_nonexistent_pipeline(runner, tmp_path):
    """Test error handling for nonexistent pipeline."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        result = runner.invoke(
            app, ["run", "nonexistent", "--jn", str(jn_path)]
        )

    assert result.exit_code == 1
    assert "Error" in result.output


def test_run_pipeline_with_failing_source(
    runner, tmp_path, failing_source, pass_converter, cat_target
):
    """Test error handling when source fails."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        add_exec_source(
            runner,
            jn_path,
            "failing",
            failing_source.exec.argv,
        )
        add_converter(runner, jn_path, "pass", pass_converter.jq.expr or ".")
        add_exec_target(runner, jn_path, "cat", cat_target.exec.argv)
        add_pipeline(
            runner,
            jn_path,
            "fail_pipeline",
            ["source:failing", "converter:pass", "target:cat"],
        )

        result = runner.invoke(
            app, ["run", "fail_pipeline", "--jn", str(jn_path)]
        )

    assert result.exit_code == 1
    assert "Error" in result.output
