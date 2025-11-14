import json


def test_tail_from_stdin(invoke, sample_ndjson):
    res = invoke(["tail", "1"], input_data=sample_ndjson)
    assert res.exit_code == 0
    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 1
    assert json.loads(lines[0])["name"] == "Bob"


def test_tail_from_file(invoke, people_csv):
    res = invoke(["tail", str(people_csv), "-n", "2"])  # reads via plugin
    assert res.exit_code == 0
    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 2


def test_tail_file_not_found(invoke):
    """Test tail with non-existent file."""
    result = invoke(["tail", "/nonexistent/file.csv"])
    assert result.exit_code == 1
    assert "Error:" in result.output


def test_tail_unsupported_format(invoke, tmp_path):
    """Test tail with unsupported file format."""
    unknown_file = tmp_path / "test.unknownext"
    unknown_file.write_text("some content")
    result = invoke(["tail", str(unknown_file)])
    assert result.exit_code == 1
    assert "Error:" in result.output
