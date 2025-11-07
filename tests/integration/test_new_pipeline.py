"""End-to-end tests for jn new pipeline command."""

import json

from jn.cli import app


def test_new_pipeline_basic(runner, tmp_path):
    """Test creating a basic pipeline with source -> converter -> target."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])

        # Create components first
        runner.invoke(
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
        runner.invoke(
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
        runner.invoke(
            app,
            [
                "new",
                "target",
                "test.cat",
                "exec",
                "--argv",
                "cat",
                "--jn",
                str(jn_path),
            ],
        )

        # Create pipeline
        result = runner.invoke(
            app,
            [
                "new",
                "pipeline",
                "test_pipe",
                "--steps",
                "source:test.echo",
                "--steps",
                "converter:test.pass",
                "--steps",
                "target:test.cat",
                "--jn",
                str(jn_path),
            ],
        )

    assert result.exit_code == 0
    assert "Created pipeline" in result.output or "test_pipe" in result.output

    data = json.loads(jn_path.read_text())
    assert len(data["pipelines"]) == 1
    assert data["pipelines"][0]["name"] == "test_pipe"
    assert len(data["pipelines"][0]["steps"]) == 3
    assert data["pipelines"][0]["steps"][0]["type"] == "source"
    assert data["pipelines"][0]["steps"][0]["ref"] == "test.echo"
    assert data["pipelines"][0]["steps"][1]["type"] == "converter"
    assert data["pipelines"][0]["steps"][1]["ref"] == "test.pass"
    assert data["pipelines"][0]["steps"][2]["type"] == "target"
    assert data["pipelines"][0]["steps"][2]["ref"] == "test.cat"


def test_new_pipeline_with_multiple_converters(runner, tmp_path):
    """Test creating a pipeline with multiple converters."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        runner.invoke(
            app,
            [
                "new",
                "source",
                "src",
                "exec",
                "--argv",
                "echo",
                "--jn",
                str(jn_path),
            ],
        )
        runner.invoke(
            app,
            ["new", "converter", "c1", "--expr", ".", "--jn", str(jn_path)],
        )
        runner.invoke(
            app,
            ["new", "converter", "c2", "--expr", ".x", "--jn", str(jn_path)],
        )
        runner.invoke(
            app,
            [
                "new",
                "target",
                "tgt",
                "exec",
                "--argv",
                "cat",
                "--jn",
                str(jn_path),
            ],
        )

        result = runner.invoke(
            app,
            [
                "new",
                "pipeline",
                "multi",
                "--steps",
                "source:src",
                "--steps",
                "converter:c1",
                "--steps",
                "converter:c2",
                "--steps",
                "target:tgt",
                "--jn",
                str(jn_path),
            ],
        )

    assert result.exit_code == 0
    data = json.loads(jn_path.read_text())
    assert len(data["pipelines"][0]["steps"]) == 4


def test_new_pipeline_duplicate_name(runner, tmp_path):
    """Test error handling for duplicate pipeline names."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        runner.invoke(
            app,
            [
                "new",
                "source",
                "src",
                "exec",
                "--argv",
                "echo",
                "--jn",
                str(jn_path),
            ],
        )
        runner.invoke(
            app, ["new", "converter", "c", "--expr", ".", "--jn", str(jn_path)]
        )
        runner.invoke(
            app,
            [
                "new",
                "target",
                "tgt",
                "exec",
                "--argv",
                "cat",
                "--jn",
                str(jn_path),
            ],
        )

        # Create first pipeline
        runner.invoke(
            app,
            [
                "new",
                "pipeline",
                "dup",
                "--steps",
                "source:src",
                "--steps",
                "converter:c",
                "--steps",
                "target:tgt",
                "--jn",
                str(jn_path),
            ],
        )

        # Try to create duplicate
        result = runner.invoke(
            app,
            [
                "new",
                "pipeline",
                "dup",
                "--steps",
                "source:src",
                "--steps",
                "target:tgt",
                "--jn",
                str(jn_path),
            ],
        )

    assert result.exit_code == 1
    assert result.exception is not None
    assert "already exists" in str(result.exception)


def test_new_pipeline_invalid_step_format(runner, tmp_path):
    """Test error handling for invalid step format."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])

        result = runner.invoke(
            app,
            [
                "new",
                "pipeline",
                "bad",
                "--steps",
                "invalid_format",
                "--jn",
                str(jn_path),
            ],
        )

    assert result.exit_code == 1
    assert result.exception is not None
    assert "format" in str(result.exception).lower()


def test_new_pipeline_requires_steps(runner, tmp_path):
    """Test that pipeline requires at least one step."""
    jn_path = tmp_path / "jn.json"
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])

        result = runner.invoke(
            app,
            [
                "new",
                "pipeline",
                "empty",
                "--jn",
                str(jn_path),
            ],
        )

    # Typer returns exit code 2 for missing required arguments
    assert result.exit_code == 2
    assert "steps" in result.output.lower()
