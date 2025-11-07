"""End-to-end tests for jn run command."""

import json

from jn.cli import app


def test_run_echo_pipeline(runner, tmp_path):
    """Test running a simple echo pipeline."""
    jn_path = tmp_path / "jn.json"

    project = {
        "version": "0.1",
        "name": "test",
        "sources": [
            {
                "name": "echo",
                "driver": "exec",
                "exec": {
                    "argv": [
                        "python",
                        "-c",
                        "import json; print(json.dumps({'x': 1})); print(json.dumps({'x': 2}))",
                    ]
                },
            }
        ],
        "converters": [{"name": "pass", "engine": "jq", "jq": {"expr": "."}}],
        "targets": [
            {"name": "cat", "driver": "exec", "exec": {"argv": ["cat"]}}
        ],
        "pipelines": [
            {
                "name": "echo_to_cat",
                "steps": [
                    {"type": "source", "ref": "echo"},
                    {"type": "converter", "ref": "pass"},
                    {"type": "target", "ref": "cat"},
                ],
            }
        ],
    }
    jn_path.write_text(json.dumps(project))

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app, ["run", "echo_to_cat", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0, f"Pipeline failed: {result.output}"
    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"x": 1}
    assert json.loads(lines[1]) == {"x": 2}


def test_run_pipeline_with_jq_transform(runner, tmp_path):
    """Test running a pipeline with jq transformation."""
    jn_path = tmp_path / "jn.json"

    project = {
        "version": "0.1",
        "name": "test",
        "sources": [
            {
                "name": "numbers",
                "driver": "exec",
                "exec": {
                    "argv": [
                        "python",
                        "-c",
                        "import json; print(json.dumps({'n': 1})); print(json.dumps({'n': 2}))",
                    ]
                },
            }
        ],
        "converters": [
            {"name": "double", "engine": "jq", "jq": {"expr": "{n: (.n * 2)}"}}
        ],
        "targets": [
            {"name": "stdout", "driver": "exec", "exec": {"argv": ["cat"]}}
        ],
        "pipelines": [
            {
                "name": "double_numbers",
                "steps": [
                    {"type": "source", "ref": "numbers"},
                    {"type": "converter", "ref": "double"},
                    {"type": "target", "ref": "stdout"},
                ],
            }
        ],
    }
    jn_path.write_text(json.dumps(project))

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app, ["run", "double_numbers", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0, f"Pipeline failed: {result.output}"
    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"n": 2}
    assert json.loads(lines[1]) == {"n": 4}


def test_run_nonexistent_pipeline(runner, tmp_path):
    """Test error handling for nonexistent pipeline."""
    jn_path = tmp_path / "jn.json"

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["init", "--jn", str(jn_path)])
        assert result.exit_code == 0

        result = runner.invoke(
            app, ["run", "nonexistent", "--jn", str(jn_path)]
        )

    assert result.exit_code == 1
    assert "Error" in result.output


def test_run_pipeline_with_failing_source(runner, tmp_path):
    """Test error handling when source fails."""
    jn_path = tmp_path / "jn.json"

    project = {
        "version": "0.1",
        "name": "test",
        "sources": [
            {"name": "failing", "driver": "exec", "exec": {"argv": ["false"]}}
        ],
        "converters": [{"name": "pass", "engine": "jq", "jq": {"expr": "."}}],
        "targets": [
            {"name": "stdout", "driver": "exec", "exec": {"argv": ["cat"]}}
        ],
        "pipelines": [
            {
                "name": "fail_pipeline",
                "steps": [
                    {"type": "source", "ref": "failing"},
                    {"type": "converter", "ref": "pass"},
                    {"type": "target", "ref": "stdout"},
                ],
            }
        ],
    }
    jn_path.write_text(json.dumps(project))

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app, ["run", "fail_pipeline", "--jn", str(jn_path)]
        )

    assert result.exit_code == 1
    assert "Error" in result.output
