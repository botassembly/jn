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


def test_run_pipeline_with_params(
    runner, tmp_path, pass_converter, cat_target
):
    """Test running a pipeline with --param substitution."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Source that echoes a parameter value
        add_exec_source(
            runner,
            jn_path,
            "echo_param",
            [
                "python",
                "-c",
                "import json; print(json.dumps({'msg': '${params.message}'}))",
            ],
        )
        add_converter(runner, jn_path, "pass", pass_converter.jq.expr or ".")
        add_exec_target(runner, jn_path, "cat", cat_target.exec.argv)
        add_pipeline(
            runner,
            jn_path,
            "param_pipeline",
            ["source:echo_param", "converter:pass", "target:cat"],
        )

        result = runner.invoke(
            app,
            [
                "run",
                "param_pipeline",
                "--param",
                "message=hello world",
                "--jn",
                str(jn_path),
            ],
        )

    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"msg": "hello world"}


def test_run_pipeline_with_file_driver(runner, tmp_path, pass_converter):
    """Test running a pipeline with file source and target."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create a test input file
        input_file = tmp_path / "input.ndjson"
        input_file.write_text('{"x": 1}\n{"x": 2}\n')

        # Create output directory
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        output_file = output_dir / "output.ndjson"

        # Create file source
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "file",
                "read_input",
                "--path",
                str(input_file),
                "--allow-outside-config",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        add_converter(runner, jn_path, "pass", pass_converter.jq.expr or ".")

        # Create file target
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "file",
                "write_output",
                "--path",
                str(output_file),
                "--create-parents",
                "--allow-outside-config",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        add_pipeline(
            runner,
            jn_path,
            "file_pipeline",
            ["source:read_input", "converter:pass", "target:write_output"],
        )

        # Run the pipeline
        result = runner.invoke(
            app, ["run", "file_pipeline", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    # Verify output file was created
    assert output_file.exists()
    output_content = output_file.read_text()
    lines = [line for line in output_content.strip().split("\n") if line]
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"x": 1}
    assert json.loads(lines[1]) == {"x": 2}
