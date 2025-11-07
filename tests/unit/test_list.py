"""Tests for jn list command."""

from pathlib import Path

from jn.cli import app


def test_list_sources(runner, tmp_path):
    """Test that jn list sources shows source names."""
    jn_path = tmp_path / "jn.json"

    # Create a project with init
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["init", "--jn", str(jn_path)])
        assert result.exit_code == 0

        # List sources
        result = runner.invoke(app, ["list", "sources", "--jn", str(jn_path)])

    assert result.exit_code == 0
    assert "echo.ndjson" in result.output


def test_list_targets(runner, tmp_path):
    """Test that jn list targets shows target names."""
    jn_path = tmp_path / "jn.json"

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["init", "--jn", str(jn_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["list", "targets", "--jn", str(jn_path)])

    assert result.exit_code == 0
    assert "cat" in result.output


def test_list_converters(runner, tmp_path):
    """Test that jn list converters shows converter names."""
    jn_path = tmp_path / "jn.json"

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["init", "--jn", str(jn_path)])
        assert result.exit_code == 0

        result = runner.invoke(
            app, ["list", "converters", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    assert "pass" in result.output


def test_list_pipelines(runner, tmp_path):
    """Test that jn list pipelines shows pipeline names."""
    jn_path = tmp_path / "jn.json"

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["init", "--jn", str(jn_path)])
        assert result.exit_code == 0

        result = runner.invoke(
            app, ["list", "pipelines", "--jn", str(jn_path)]
        )

    assert result.exit_code == 0
    assert "echo_to_cat" in result.output


def test_list_empty_collection(runner, tmp_path):
    """Test that jn list shows message for empty collections."""
    jn_path = tmp_path / "jn.json"

    # Create minimal project with no sources
    import json

    jn_path.write_text(
        json.dumps(
            {
                "version": "0.1",
                "name": "empty",
                "sources": [],
                "targets": [],
                "converters": [],
                "pipelines": [],
            }
        )
    )

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["list", "sources", "--jn", str(jn_path)])

    assert result.exit_code == 0
    assert "No sources defined" in result.output
