import json
from pathlib import Path


def test_run_csv_to_json(invoke, people_csv, tmp_path):
    out = tmp_path / "out.json"
    res = invoke(["run", str(people_csv), str(out)])
    assert res.exit_code == 0
    data = json.loads(Path(out).read_text())
    assert len(data) == 5
    assert data[0]["name"] == "Alice"


def test_run_with_custom_home(invoke, people_csv, jn_home, tmp_path):
    out = tmp_path / "out.json"
    res = invoke(["--home", str(jn_home), "run", str(people_csv), str(out)])
    assert res.exit_code == 0
    data = json.loads(Path(out).read_text())
    assert len(data) == 5


def test_run_input_file_not_found(invoke, tmp_path):
    """Test run with non-existent input file."""
    out = tmp_path / "out.json"
    result = invoke(["run", "/nonexistent/input.csv", str(out)])
    assert result.exit_code == 1
    assert "Error:" in result.output


def test_run_unsupported_input_format(invoke, tmp_path):
    """Test run with unsupported input format."""
    in_file = tmp_path / "input.unknownext"
    in_file.write_text("some content")
    out_file = tmp_path / "out.json"
    result = invoke(["run", str(in_file), str(out_file)])
    assert result.exit_code == 1
    assert "Error:" in result.output


def test_run_unsupported_output_format(invoke, people_csv, tmp_path):
    """Test run with unsupported output format."""
    out_file = tmp_path / "out.unknownext"
    result = invoke(["run", str(people_csv), str(out_file)])
    assert result.exit_code == 1
    assert "Error:" in result.output
