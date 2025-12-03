"""Integration tests for Zig CSV binary plugin."""

import json
import subprocess

import pytest

from src.jn.zig_builder import get_or_build_plugin


@pytest.fixture(scope="module")
def csv_binary():
    """Get or build the CSV plugin binary."""
    binary = get_or_build_plugin("csv")
    if not binary:
        pytest.skip("Zig CSV binary not available (Zig compiler required)")
    return str(binary)


# --jn-meta tests


def test_jn_meta_outputs_valid_json(csv_binary):
    """--jn-meta should output valid JSON."""
    result = subprocess.run(
        [csv_binary, "--jn-meta"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    meta = json.loads(result.stdout)
    assert isinstance(meta, dict)


def test_jn_meta_contains_required_fields(csv_binary):
    """Metadata should contain required fields."""
    result = subprocess.run(
        [csv_binary, "--jn-meta"],
        capture_output=True,
        text=True,
    )
    meta = json.loads(result.stdout)
    assert meta["name"] == "csv"
    assert "matches" in meta
    assert "role" in meta
    assert meta["role"] == "format"
    assert "modes" in meta
    assert "read" in meta["modes"]
    assert "write" in meta["modes"]


def test_jn_meta_matches_csv_extensions(csv_binary):
    """Should match .csv and .tsv files."""
    result = subprocess.run(
        [csv_binary, "--jn-meta"],
        capture_output=True,
        text=True,
    )
    meta = json.loads(result.stdout)
    matches = meta["matches"]
    assert any(".csv" in m for m in matches)
    assert any(".tsv" in m for m in matches)


# --mode=read tests


def test_read_simple_csv(csv_binary):
    """Should parse simple CSV to NDJSON."""
    input_data = "name,age\nAlice,30\nBob,25\n"
    result = subprocess.run(
        [csv_binary, "--mode=read"],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"name": "Alice", "age": "30"}
    assert json.loads(lines[1]) == {"name": "Bob", "age": "25"}


def test_read_csv_with_quotes(csv_binary):
    """Should handle quoted fields."""
    input_data = 'name,city\n"Alice Smith","New York"\nBob,LA\n'
    result = subprocess.run(
        [csv_binary, "--mode=read"],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["city"] == "New York"


def test_read_csv_with_delimiter_in_quotes(csv_binary):
    """Should handle comma inside quoted field."""
    input_data = 'name,note\nAlice,"Hello, World"\n'
    result = subprocess.run(
        [csv_binary, "--mode=read"],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    record = json.loads(result.stdout.strip())
    assert record["note"] == "Hello, World"


def test_read_tsv_with_tab_delimiter(csv_binary):
    """Should parse TSV with tab delimiter."""
    input_data = "name\tage\nAlice\t30\n"
    result = subprocess.run(
        [csv_binary, "--mode=read", "--delimiter=tab"],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    record = json.loads(result.stdout.strip())
    assert record == {"name": "Alice", "age": "30"}


def test_read_csv_empty_input(csv_binary):
    """Should handle empty input."""
    result = subprocess.run(
        [csv_binary, "--mode=read"],
        input="",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_read_csv_header_only(csv_binary):
    """Should handle CSV with header but no data."""
    input_data = "name,age\n"
    result = subprocess.run(
        [csv_binary, "--mode=read"],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_read_csv_no_header(csv_binary):
    """Should handle --no-header flag."""
    input_data = "Alice,30\nBob,25\n"
    result = subprocess.run(
        [csv_binary, "--mode=read", "--no-header"],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 2
    # Should use col0, col1, etc. as keys
    record = json.loads(lines[0])
    assert "col0" in record
    assert record["col0"] == "Alice"


# --mode=write tests


def test_write_simple_ndjson(csv_binary):
    """Should write NDJSON to CSV."""
    input_data = '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'
    result = subprocess.run(
        [csv_binary, "--mode=write"],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 3  # header + 2 rows
    # Header should contain both field names
    assert "name" in lines[0]
    assert "age" in lines[0]


def test_write_empty_input(csv_binary):
    """Should handle empty input."""
    result = subprocess.run(
        [csv_binary, "--mode=write"],
        input="",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


# Integration with jn CLI


def test_jn_cat_uses_zig_csv(tmp_path):
    """jn cat should use Zig CSV plugin."""
    # Create test file
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("x,y\n1,2\n3,4\n")

    result = subprocess.run(
        ["jn", "cat", str(csv_file)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 2
    # Zig plugin outputs without spaces (Python has spaces)
    assert json.loads(lines[0]) == {"x": "1", "y": "2"}


def test_jn_put_uses_zig_csv(tmp_path):
    """jn put should use Zig CSV plugin."""
    csv_file = tmp_path / "out.csv"
    input_data = '{"a":"1","b":"2"}\n'

    result = subprocess.run(
        ["jn", "put", str(csv_file)],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    content = csv_file.read_text()
    lines = content.strip().split("\n")
    assert len(lines) == 2  # header + 1 row
