from jn.cli import app
from tests.helpers import (
    add_converter,
    add_exec_source,
    add_exec_target,
    add_pipeline,
    init_config,
)


def test_list_sources(runner, tmp_path):
    """`jn list sources` returns configured source names."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        add_exec_source(
            runner,
            jn_path,
            "echo",
            [
                "python",
                "-c",
                "import json,sys;print(json.dumps({'x': 1}));print(json.dumps({'x': 2}))",
            ],
        )

        result = runner.invoke(app, ["list", "sources", "--jn", str(jn_path)])

    assert result.exit_code == 0
    assert "echo" in result.output


def test_list_targets(runner, tmp_path):
    """`jn list targets` returns configured target names."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        add_exec_target(
            runner,
            jn_path,
            "cat",
            [
                "python",
                "-c",
                "import sys; sys.stdout.write(sys.stdin.read())",
            ],
        )

        result = runner.invoke(app, ["list", "targets", "--jn", str(jn_path)])

    assert result.exit_code == 0
    assert "cat" in result.output


def test_list_converters(runner, tmp_path):
    """`jn list converters` returns configured converter names."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        add_converter(runner, jn_path, "pass", ".")

        result = runner.invoke(
            app, ["list", "converters", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    assert "pass" in result.output


def test_list_pipelines(runner, tmp_path):
    """`jn list pipelines` returns configured pipeline names."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        add_exec_source(
            runner,
            jn_path,
            "echo",
            [
                "python",
                "-c",
                "import json;print(json.dumps({'x': 1}))",
            ],
        )
        add_exec_target(runner, jn_path, "cat", ["cat"])
        add_pipeline(
            runner,
            jn_path,
            "demo",
            ["source:echo", "target:cat"],
        )

        result = runner.invoke(
            app, ["list", "pipelines", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    assert "demo" in result.output


def test_list_empty_collection(runner, tmp_path):
    """Empty collections show a friendly message."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)
        result = runner.invoke(app, ["list", "sources", "--jn", str(jn_path)])

    assert result.exit_code == 0
    assert "No sources defined" in result.output
