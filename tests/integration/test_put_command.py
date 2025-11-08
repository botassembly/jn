"""Tests for jn put command - full integration testing."""

import json
from pathlib import Path

from jn.cli import app


def test_put_writes_json_array(runner, tmp_path):
    """Test writing NDJSON to JSON array format."""
    output_file = tmp_path / "output.json"

    result = runner.invoke(
        app,
        ["put", str(output_file)],
        input='{"x": 1}\n{"x": 2}\n',
    )

    assert result.exit_code == 0
    assert "Wrote" in result.output

    # Verify file contents
    content = json.loads(output_file.read_text())
    assert isinstance(content, list)
    assert len(content) == 2
    assert content[0] == {"x": 1}
    assert content[1] == {"x": 2}


def test_put_writes_pretty_json(runner, tmp_path):
    """Test writing pretty-printed JSON."""
    output_file = tmp_path / "output.json"

    result = runner.invoke(
        app,
        ["put", str(output_file), "--pretty"],
        input='{"name": "Alice", "age": 30}\n',
    )

    assert result.exit_code == 0

    content = output_file.read_text()
    assert "{\n" in content  # Pretty-printed
    assert '"name": "Alice"' in content

    # Verify parseable
    data = json.loads(content)
    assert data[0]["name"] == "Alice"


def test_put_writes_csv_with_header(runner, tmp_path):
    """Test writing NDJSON to CSV format."""
    output_file = tmp_path / "output.csv"

    result = runner.invoke(
        app,
        ["put", str(output_file)],
        input='{"name": "Alice", "age": 30}\n{"name": "Bob", "age": 25}\n',
    )

    assert result.exit_code == 0

    lines = output_file.read_text().strip().split("\n")
    assert len(lines) == 3
    assert "name,age" in lines[0]
    assert "Alice,30" in lines[1]
    assert "Bob,25" in lines[2]


def test_put_writes_csv_without_header(runner, tmp_path):
    """Test writing CSV without header row."""
    output_file = tmp_path / "output.csv"

    result = runner.invoke(
        app,
        ["put", str(output_file), "--no-header"],
        input='{"name": "Alice"}\n{"name": "Bob"}\n',
    )

    assert result.exit_code == 0

    lines = output_file.read_text().strip().split("\n")
    assert len(lines) == 2
    assert "name" not in lines[0]  # No header
    assert "Alice" in lines[0]
    assert "Bob" in lines[1]


def test_put_writes_tsv(runner, tmp_path):
    """Test writing TSV format."""
    output_file = tmp_path / "output.tsv"

    result = runner.invoke(
        app,
        ["put", str(output_file)],
        input='{"a": 1, "b": 2}\n',
    )

    assert result.exit_code == 0

    content = output_file.read_text()
    assert "\t" in content  # Tab-separated
    assert "a\tb" in content


def test_put_writes_ndjson(runner, tmp_path):
    """Test writing NDJSON format."""
    output_file = tmp_path / "output.ndjson"

    result = runner.invoke(
        app,
        ["put", str(output_file)],
        input='{"x": 1}\n{"x": 2}\n',
    )

    assert result.exit_code == 0

    lines = output_file.read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"x": 1}
    assert json.loads(lines[1]) == {"x": 2}


def test_put_auto_detects_format_from_extension(runner, tmp_path):
    """Test format auto-detection from file extension."""
    # CSV
    csv_file = tmp_path / "data.csv"
    runner.invoke(app, ["put", str(csv_file)], input='{"x": 1, "y": 2}\n')
    content = csv_file.read_text()
    assert "x,y" in content  # Has header with comma
    assert "1,2" in content  # Data row with comma

    # JSON
    json_file = tmp_path / "data.json"
    runner.invoke(app, ["put", str(json_file)], input='{"x": 1}\n')
    assert json.loads(json_file.read_text()) == [{"x": 1}]

    # NDJSON
    ndjson_file = tmp_path / "data.jsonl"
    runner.invoke(app, ["put", str(ndjson_file)], input='{"x": 1}\n{"x": 2}\n')
    lines = ndjson_file.read_text().strip().split("\n")
    assert len(lines) == 2


def test_put_with_custom_delimiter(runner, tmp_path):
    """Test CSV with custom delimiter."""
    output_file = tmp_path / "output.csv"

    result = runner.invoke(
        app,
        ["put", str(output_file), "--delimiter", "|"],
        input='{"a": 1, "b": 2}\n',
    )

    assert result.exit_code == 0

    content = output_file.read_text()
    assert "|" in content
    assert "a|b" in content


def test_put_appends_to_existing_ndjson(runner, tmp_path):
    """Test appending to existing NDJSON file."""
    output_file = tmp_path / "output.ndjson"
    output_file.write_text('{"existing": 1}\n')

    result = runner.invoke(
        app,
        ["put", str(output_file), "--append"],
        input='{"new": 2}\n',
    )

    assert result.exit_code == 0

    lines = output_file.read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"existing": 1}
    assert json.loads(lines[1]) == {"new": 2}


def test_put_requires_format_for_stdout(runner, tmp_path):
    """Test that writing to stdout requires --format flag."""
    result = runner.invoke(app, ["put", "-"], input='{"x": 1}\n')

    assert result.exit_code == 1
    assert "--format is required" in result.output


def test_put_error_on_existing_file_without_overwrite(runner, tmp_path):
    """Test that put fails on existing file without --overwrite or --append."""
    output_file = tmp_path / "output.json"
    output_file.write_text("[]")

    result = runner.invoke(
        app,
        ["put", str(output_file), "--no-overwrite"],
        input='{"x": 1}\n',
    )

    assert result.exit_code == 1
    assert "already exists" in result.output


def test_put_overwrites_with_overwrite_flag(runner, tmp_path):
    """Test that put overwrites existing file with --overwrite."""
    output_file = tmp_path / "output.json"
    output_file.write_text('[{"old": 1}]')

    result = runner.invoke(
        app,
        ["put", str(output_file), "--overwrite"],
        input='{"new": 2}\n',
    )

    assert result.exit_code == 0

    content = json.loads(output_file.read_text())
    assert content == [{"new": 2}]
    assert {"old": 1} not in content


def test_put_handles_empty_input(runner, tmp_path):
    """Test writing empty input."""
    output_file = tmp_path / "output.json"

    result = runner.invoke(
        app,
        ["put", str(output_file)],
        input='',
    )

    assert result.exit_code == 0
    content = json.loads(output_file.read_text())
    assert content == []


def test_put_handles_complex_nested_objects(runner, tmp_path):
    """Test writing complex nested JSON objects."""
    output_file = tmp_path / "output.json"

    complex_data = {
        "user": {"name": "Alice", "roles": ["admin", "user"]},
        "metadata": {"created": "2024-01-01", "tags": ["important"]},
    }

    result = runner.invoke(
        app,
        ["put", str(output_file)],
        input=json.dumps(complex_data) + '\n',
    )

    assert result.exit_code == 0

    content = json.loads(output_file.read_text())
    assert content[0] == complex_data
