"""Tests for jn list command."""

from jn.cli import app
from jn.models.project import (
    Converter,
    ExecSpec,
    JqConfig,
    Pipeline,
    Project,
    Source,
    Target,
)


def test_list_sources(runner, tmp_path):
    """Test that jn list sources shows source names."""
    jn_path = tmp_path / "jn.json"
    project = Project(
        version="0.1",
        name="test",
        sources=[
            Source(name="foo", driver="exec", exec=ExecSpec(argv=["echo"]))
        ],
    )
    jn_path.write_text(project.model_dump_json())

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["list", "sources", "--jn", str(jn_path)])

    assert result.exit_code == 0
    assert "foo" in result.output


def test_list_targets(runner, tmp_path):
    """Test that jn list targets shows target names."""
    jn_path = tmp_path / "jn.json"
    project = Project(
        version="0.1",
        name="test",
        targets=[
            Target(name="bar", driver="exec", exec=ExecSpec(argv=["cat"]))
        ],
    )
    jn_path.write_text(project.model_dump_json())

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["list", "targets", "--jn", str(jn_path)])

    assert result.exit_code == 0
    assert "bar" in result.output


def test_list_converters(runner, tmp_path):
    """Test that jn list converters shows converter names."""
    jn_path = tmp_path / "jn.json"
    project = Project(
        version="0.1",
        name="test",
        converters=[
            Converter(name="transform", engine="jq", jq=JqConfig(expr="."))
        ],
    )
    jn_path.write_text(project.model_dump_json())

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app, ["list", "converters", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    assert "transform" in result.output


def test_list_pipelines(runner, tmp_path):
    """Test that jn list pipelines shows pipeline names."""
    jn_path = tmp_path / "jn.json"
    project = Project(
        version="0.1",
        name="test",
        pipelines=[Pipeline(name="my_pipeline", steps=[])],
    )
    jn_path.write_text(project.model_dump_json())

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app, ["list", "pipelines", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    assert "my_pipeline" in result.output


def test_list_empty_collection(runner, tmp_path):
    """Test that jn list shows message for empty collections."""
    jn_path = tmp_path / "jn.json"

    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(app, ["list", "sources", "--jn", str(jn_path)])

    assert result.exit_code == 0
    assert "No sources defined" in result.output
