"""End-to-end tests for jn run command."""

import json

from jn.cli import app
from jn.models.project import (
    Converter,
    ExecSpec,
    JqConfig,
    Pipeline,
    Project,
    Source,
    Step,
    Target,
)


def test_run_echo_pipeline(runner, tmp_path):
    """Test running a simple echo pipeline."""
    jn_path = tmp_path / "jn.json"

    project = Project(
        version="0.1",
        name="test",
        sources=[
            Source(
                name="echo",
                driver="exec",
                exec=ExecSpec(
                    argv=[
                        "python",
                        "-c",
                        "import json; print(json.dumps({'x': 1})); print(json.dumps({'x': 2}))",
                    ]
                ),
            )
        ],
        converters=[
            Converter(name="pass", engine="jq", jq=JqConfig(expr="."))
        ],
        targets=[
            Target(name="cat", driver="exec", exec=ExecSpec(argv=["cat"]))
        ],
        pipelines=[
            Pipeline(
                name="echo_to_cat",
                steps=[
                    Step(type="source", ref="echo"),
                    Step(type="converter", ref="pass"),
                    Step(type="target", ref="cat"),
                ],
            )
        ],
    )
    jn_path.write_text(project.model_dump_json(indent=2))

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app, ["run", "echo_to_cat", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"x": 1}
    assert json.loads(lines[1]) == {"x": 2}


def test_run_pipeline_with_jq_transform(runner, tmp_path):
    """Test running a pipeline with jq transformation."""
    jn_path = tmp_path / "jn.json"

    project = Project(
        version="0.1",
        name="test",
        sources=[
            Source(
                name="numbers",
                driver="exec",
                exec=ExecSpec(
                    argv=[
                        "python",
                        "-c",
                        "import json; print(json.dumps({'n': 1})); print(json.dumps({'n': 2}))",
                    ]
                ),
            )
        ],
        converters=[
            Converter(
                name="double", engine="jq", jq=JqConfig(expr="{n: (.n * 2)}")
            )
        ],
        targets=[
            Target(name="stdout", driver="exec", exec=ExecSpec(argv=["cat"]))
        ],
        pipelines=[
            Pipeline(
                name="double_numbers",
                steps=[
                    Step(type="source", ref="numbers"),
                    Step(type="converter", ref="double"),
                    Step(type="target", ref="stdout"),
                ],
            )
        ],
    )
    jn_path.write_text(project.model_dump_json(indent=2))

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app, ["run", "double_numbers", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line]
    assert json.loads(lines[0]) == {"n": 2}
    assert json.loads(lines[1]) == {"n": 4}


def test_run_nonexistent_pipeline(runner, tmp_path):
    """Test error handling for nonexistent pipeline."""
    jn_path = tmp_path / "jn.json"

    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["init", "--jn", str(jn_path)])
        result = runner.invoke(
            app, ["run", "nonexistent", "--jn", str(jn_path)]
        )

    assert result.exit_code == 1
    assert "Error" in result.output


def test_run_pipeline_with_failing_source(runner, tmp_path):
    """Test error handling when source fails."""
    jn_path = tmp_path / "jn.json"

    project = Project(
        version="0.1",
        name="test",
        sources=[
            Source(
                name="failing", driver="exec", exec=ExecSpec(argv=["false"])
            )
        ],
        converters=[
            Converter(name="pass", engine="jq", jq=JqConfig(expr="."))
        ],
        targets=[
            Target(name="stdout", driver="exec", exec=ExecSpec(argv=["cat"]))
        ],
        pipelines=[
            Pipeline(
                name="fail_pipeline",
                steps=[
                    Step(type="source", ref="failing"),
                    Step(type="converter", ref="pass"),
                    Step(type="target", ref="stdout"),
                ],
            )
        ],
    )
    jn_path.write_text(project.model_dump_json(indent=2))

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app, ["run", "fail_pipeline", "--jn", str(jn_path)]
        )

    assert result.exit_code == 1
    assert "Error" in result.output
