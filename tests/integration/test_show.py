"""End-to-end tests for jn show command."""

import json

from jn.cli import app
from jn.models.project import Project


def test_show_source(runner, tmp_path, echo_source):
    """Test that jn show source displays source JSON."""
    jn_path = tmp_path / "jn.json"
    project = Project(
        version="0.1",
        name="test",
        sources=[echo_source],
    )
    jn_path.write_text(project.model_dump_json())

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app, ["show", "source", "echo", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    output_data = json.loads(result.output)
    assert output_data["name"] == "echo"
    assert output_data["driver"] == "exec"


def test_show_target(runner, tmp_path, cat_target):
    """Test that jn show target displays target JSON."""
    jn_path = tmp_path / "jn.json"
    project = Project(
        version="0.1",
        name="test",
        targets=[cat_target],
    )
    jn_path.write_text(project.model_dump_json())

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app, ["show", "target", "cat", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    output_data = json.loads(result.output)
    assert output_data["name"] == "cat"
    assert output_data["driver"] == "exec"


def test_show_converter(runner, tmp_path, pass_converter):
    """Test that jn show converter displays converter JSON."""
    jn_path = tmp_path / "jn.json"
    project = Project(
        version="0.1",
        name="test",
        converters=[pass_converter],
    )
    jn_path.write_text(project.model_dump_json())

    with runner.isolated_filesystem(temp_dir=tmp_path):
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
    from jn.models.project import Pipeline, Step

    jn_path = tmp_path / "jn.json"
    project = Project(
        version="0.1",
        name="test",
        sources=[echo_source],
        converters=[pass_converter],
        targets=[cat_target],
        pipelines=[
            Pipeline(
                name="test_pipeline",
                steps=[
                    Step(type="source", ref="echo"),
                    Step(type="converter", ref="pass"),
                    Step(type="target", ref="cat"),
                ],
            )
        ],
    )
    jn_path.write_text(project.model_dump_json())

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app, ["show", "pipeline", "test_pipeline", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    output_data = json.loads(result.output)
    assert output_data["name"] == "test_pipeline"
    assert len(output_data["steps"]) == 3


def test_show_nonexistent_item(runner, tmp_path):
    """Test error handling for nonexistent item."""
    jn_path = tmp_path / "jn.json"

    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(
            app, ["show", "source", "nonexistent", "--jn", str(jn_path)]
        )

    assert result.exit_code == 1
    assert "not found" in result.output or "Error" in result.output
