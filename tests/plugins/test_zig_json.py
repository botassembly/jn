"""Integration tests for Zig JSON binary plugin."""

import json
import subprocess
from pathlib import Path

import pytest


PLUGIN_DIR = Path(__file__).parent.parent.parent / "plugins" / "zig" / "json" / "bin"


@pytest.fixture(scope="module")
def json_binary():
    """Get the JSON plugin binary."""
    binary = PLUGIN_DIR / "json"
    if not binary.exists():
        pytest.skip("JSON plugin not built (run 'make zig-plugins')")
    return str(binary)


# --jn-meta tests


def test_jn_meta_outputs_valid_json(json_binary):
    """--jn-meta should output valid JSON."""
    result = subprocess.run(
        [json_binary, "--jn-meta"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    meta = json.loads(result.stdout)
    assert isinstance(meta, dict)


def test_jn_meta_contains_required_fields(json_binary):
    """Metadata should contain required fields."""
    result = subprocess.run(
        [json_binary, "--jn-meta"],
        capture_output=True,
        text=True,
    )
    meta = json.loads(result.stdout)
    assert meta["name"] == "json"
    assert "matches" in meta
    assert "role" in meta
    assert meta["role"] == "format"


def test_jn_meta_matches_json_extension(json_binary):
    """Should match .json files."""
    result = subprocess.run(
        [json_binary, "--jn-meta"],
        capture_output=True,
        text=True,
    )
    meta = json.loads(result.stdout)
    matches = meta["matches"]
    assert any(".json" in m for m in matches)


# --mode=read tests


def test_read_json_array(json_binary):
    """Should convert JSON array to NDJSON lines."""
    input_data = '[{"id":1},{"id":2},{"id":3}]'
    result = subprocess.run(
        [json_binary, "--mode=read"],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 3
    assert json.loads(lines[0]) == {"id": 1}
    assert json.loads(lines[1]) == {"id": 2}
    assert json.loads(lines[2]) == {"id": 3}


def test_read_json_object(json_binary):
    """Should output single JSON object as one line."""
    input_data = '{"name":"Alice","age":30}'
    result = subprocess.run(
        [json_binary, "--mode=read"],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"name": "Alice", "age": 30}


def test_read_json_nested(json_binary):
    """Should preserve nested structures."""
    input_data = '{"user":{"name":"Bob","scores":[1,2,3]}}'
    result = subprocess.run(
        [json_binary, "--mode=read"],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    record = json.loads(result.stdout.strip())
    assert record["user"]["name"] == "Bob"
    assert record["user"]["scores"] == [1, 2, 3]


def test_read_json_empty_array(json_binary):
    """Should handle empty JSON array."""
    input_data = "[]"
    result = subprocess.run(
        [json_binary, "--mode=read"],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_read_json_empty_input(json_binary):
    """Should handle empty input."""
    result = subprocess.run(
        [json_binary, "--mode=read"],
        input="",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_read_json_with_special_chars(json_binary):
    """Should handle strings with special characters."""
    input_data = '{"text":"Hello\\nWorld","quote":"\\"test\\""}'
    result = subprocess.run(
        [json_binary, "--mode=read"],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    record = json.loads(result.stdout.strip())
    assert record["text"] == "Hello\nWorld"
    assert record["quote"] == '"test"'


def test_read_json_multiline_formatted(json_binary):
    """Should handle pretty-printed JSON."""
    input_data = """{
  "name": "Alice",
  "items": [
    1,
    2,
    3
  ]
}"""
    result = subprocess.run(
        [json_binary, "--mode=read"],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    record = json.loads(result.stdout.strip())
    assert record["name"] == "Alice"
    assert record["items"] == [1, 2, 3]


# --mode=write tests


def test_write_outputs_array_by_default(json_binary):
    """Write mode should emit a JSON array by default."""
    input_data = '{"a":1}\n{"a":2}\n'
    result = subprocess.run(
        [json_binary, "--mode=write"],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert data == [{"a": 1}, {"a": 2}]


def test_write_ndjson_format_passthrough(json_binary):
    """--format=ndjson should preserve NDJSON streaming."""
    input_data = '{"a":1}\n{"a":2}\n'
    result = subprocess.run(
        [json_binary, "--mode=write", "--format=ndjson"],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = [line for line in result.stdout.split("\n") if line]
    assert len(lines) == 2
    assert json.loads(lines[0])["a"] == 1
    assert json.loads(lines[1])["a"] == 2


def test_write_supports_indent(json_binary):
    """--indent should pretty-print the output array."""
    input_data = '{"a":1}\n{"a":2}\n'
    result = subprocess.run(
        [json_binary, "--mode=write", "--indent=2"],
        input=input_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.startswith("[\n  {")
