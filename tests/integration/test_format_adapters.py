"""Format adapter tests using fixture-based config.

All tests use the comprehensive test config from fixtures/test_config.json.
Each test is a pure function that runs a pre-configured pipeline.
"""

import json

from jn.cli import app


def test_write_json_array(runner, format_test_config):
    """Test writing NDJSON to JSON array format."""
    result = runner.invoke(app, ["run", "to_json_array", "--jn", str(format_test_config)])
    assert result.exit_code == 0

    # Check output file
    output_file = format_test_config.parent / "out" / "output.json"
    assert output_file.exists()
    content = json.loads(output_file.read_text())

    # Should be a JSON array
    assert isinstance(content, list)
    assert len(content) == 2
    assert content[0]["x"] == 1
    assert content[1]["x"] == 2


def test_write_jsonl(runner, format_test_config):
    """Test writing NDJSON to JSONL format."""
    result = runner.invoke(app, ["run", "to_jsonl", "--jn", str(format_test_config)])
    assert result.exit_code == 0

    # Check output - should be NDJSON (one object per line)
    output_file = format_test_config.parent / "out" / "output.jsonl"
    assert output_file.exists()
    lines = output_file.read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["x"] == 1
    assert json.loads(lines[1])["x"] == 2


def test_write_csv(runner, format_test_config):
    """Test writing NDJSON to CSV format."""
    result = runner.invoke(app, ["run", "to_csv", "--jn", str(format_test_config)])
    assert result.exit_code == 0

    # Check CSV output
    output_file = format_test_config.parent / "out" / "output.csv"
    assert output_file.exists()
    lines = output_file.read_text().strip().split("\n")
    assert len(lines) == 3  # header + 2 rows
    assert "name,age" in lines[0]
    assert "Alice,30" in lines[1]
    assert "Bob,25" in lines[2]


def test_write_yaml(runner, format_test_config):
    """Test writing NDJSON to YAML format."""
    result = runner.invoke(app, ["run", "to_yaml", "--jn", str(format_test_config)])
    assert result.exit_code == 0

    # Check YAML output
    output_file = format_test_config.parent / "out" / "output.yaml"
    assert output_file.exists()
    content = output_file.read_text()
    assert "Alice" in content
    assert "Bob" in content


def test_write_toml(runner, format_test_config):
    """Test writing NDJSON to TOML format."""
    result = runner.invoke(app, ["run", "to_toml", "--jn", str(format_test_config)])
    assert result.exit_code == 0

    # Check TOML output
    output_file = format_test_config.parent / "out" / "output.toml"
    assert output_file.exists()
    content = output_file.read_text()
    assert "Alice" in content
    assert "records" in content  # TOML wraps in records array


def test_write_xml(runner, format_test_config):
    """Test writing NDJSON to XML format."""
    result = runner.invoke(app, ["run", "to_xml", "--jn", str(format_test_config)])
    assert result.exit_code == 0

    # Check XML output
    output_file = format_test_config.parent / "out" / "output.xml"
    assert output_file.exists()
    content = output_file.read_text()
    assert "Alice" in content
    assert "<root>" in content


def test_roundtrip_csv_to_yaml(runner, format_test_config):
    """Test round-trip: CSV → NDJSON → YAML."""
    result = runner.invoke(app, ["run", "csv_to_yaml", "--jn", str(format_test_config)])
    assert result.exit_code == 0

    # Verify YAML output contains CSV data
    output_file = format_test_config.parent / "out" / "output.yaml"
    assert output_file.exists()
    content = output_file.read_text()
    assert "Alice" in content
    assert "Bob" in content
    assert "NYC" in content


def test_empty_input_json(runner, format_test_config):
    """Test writing empty input to JSON (should be empty array)."""
    result = runner.invoke(app, ["run", "empty_to_json", "--jn", str(format_test_config)])
    assert result.exit_code == 0

    # Should be empty array for .json
    output_file = format_test_config.parent / "out" / "output.json"
    assert output_file.exists()
    content = json.loads(output_file.read_text())
    assert content == []


def test_empty_input_csv(runner, format_test_config):
    """Test writing empty input to CSV (should be empty)."""
    result = runner.invoke(app, ["run", "empty_to_csv", "--jn", str(format_test_config)])
    assert result.exit_code == 0

    # Should be empty for CSV
    output_file = format_test_config.parent / "out" / "output.csv"
    assert output_file.exists()
    content = output_file.read_text()
    assert content == ""
