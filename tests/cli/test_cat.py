import json
from pathlib import Path


def test_cat_to_stdout(invoke, people_csv):
    result = invoke(["cat", str(people_csv)])
    assert result.exit_code == 0

    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 5
    first = json.loads(lines[0])
    assert first["name"] == "Alice"


def test_cat_then_put_pipeline(invoke, people_csv, tmp_path):
    # First run cat to get NDJSON
    cat_res = invoke(["cat", str(people_csv)])
    assert cat_res.exit_code == 0

    # Pipe into put to write JSON array
    out_file = tmp_path / "out.json"
    put_res = invoke(["put", str(out_file)], input_data=cat_res.output)
    assert put_res.exit_code == 0

    data = json.loads(Path(out_file).read_text())
    assert isinstance(data, list)
    assert len(data) == 5
    assert data[0]["name"] == "Alice"


def test_cat_file_not_found(invoke):
    """Test cat with non-existent file."""
    result = invoke(["cat", "/nonexistent/file.csv"])
    assert result.exit_code == 1
    assert "Error:" in result.output


def test_cat_unsupported_format(invoke, tmp_path):
    """Test cat with unsupported file format (no matching plugin)."""
    unknown_file = tmp_path / "test.unknownext"
    unknown_file.write_text("some content")
    result = invoke(["cat", str(unknown_file)])
    assert result.exit_code == 1
    assert "Error:" in result.output


def test_cat_txt_file_auto_detection(invoke, tmp_path):
    """Verify .txt files are auto-detected as CSV/TSV.

    This test verifies the fix for developer feedback: .txt files commonly
    contain tab-separated or comma-separated data and should be auto-detected.
    """
    # Create a tab-separated .txt file
    txt_file = tmp_path / "data.txt"
    txt_file.write_text("name\tage\nAlice\t30\nBob\t25\n")

    # Should auto-detect as CSV and parse successfully
    result = invoke(["cat", str(txt_file)])
    assert result.exit_code == 0

    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 2  # Two data rows (header is consumed)

    first = json.loads(lines[0])
    assert first["name"] == "Alice"
    assert first["age"] == "30"

    second = json.loads(lines[1])
    assert second["name"] == "Bob"
    assert second["age"] == "25"
