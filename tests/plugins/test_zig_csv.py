"""Integration tests for Zig CSV binary plugin."""

import json
import subprocess
from pathlib import Path

import pytest


# Path to plugin binary
PLUGIN_DIR = Path(__file__).parent.parent.parent / "plugins" / "zig" / "csv" / "bin"


@pytest.fixture(scope="module")
def csv_binary():
    """Get the CSV plugin binary."""
    binary = PLUGIN_DIR / "csv"
    if not binary.exists():
        pytest.skip("CSV plugin not built (run 'make zig-plugins')")
    return str(binary)


# --jn-meta tests

def test_csv_binary_meta(csv_binary):
    """Test --jn-meta outputs valid JSON manifest."""
    result = subprocess.run(
        [csv_binary, "--jn-meta"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    meta = json.loads(result.stdout)
    assert meta["name"] == "csv"
    assert "read" in meta["modes"]
    assert "write" in meta["modes"]


def test_csv_binary_meta_has_matches(csv_binary):
    """Test --jn-meta includes pattern matches."""
    result = subprocess.run(
        [csv_binary, "--jn-meta"],
        capture_output=True,
        text=True,
    )
    meta = json.loads(result.stdout)
    assert "matches" in meta
    assert any(".csv" in m for m in meta["matches"])


# Read mode tests

def test_csv_read_simple(csv_binary):
    """Test reading simple CSV data."""
    csv_data = "name,age\nAlice,30\nBob,25\n"
    result = subprocess.run(
        [csv_binary, "--mode=read"],
        input=csv_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = [l for l in result.stdout.strip().split("\n") if l]
    assert len(lines) == 2

    first = json.loads(lines[0])
    assert first["name"] == "Alice"
    assert first["age"] == "30"


def test_csv_read_quoted_fields(csv_binary):
    """Test reading CSV with quoted fields."""
    csv_data = 'name,bio\n"Alice","Has a ""nickname"""\n'
    result = subprocess.run(
        [csv_binary, "--mode=read"],
        input=csv_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = [l for l in result.stdout.strip().split("\n") if l]
    first = json.loads(lines[0])
    assert first["name"] == "Alice"
    assert 'nickname' in first["bio"]


def test_csv_read_tsv(csv_binary):
    """Test reading tab-separated data."""
    tsv_data = "name\tage\nAlice\t30\n"
    result = subprocess.run(
        [csv_binary, "--mode=read", "--delimiter=\t"],
        input=tsv_data,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = [l for l in result.stdout.strip().split("\n") if l]
    first = json.loads(lines[0])
    assert first["name"] == "Alice"


# Write mode tests

def test_csv_write_simple(csv_binary):
    """Test writing NDJSON to CSV."""
    ndjson = '{"name":"Alice","age":"30"}\n{"name":"Bob","age":"25"}\n'
    result = subprocess.run(
        [csv_binary, "--mode=write"],
        input=ndjson,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 3  # header + 2 rows
    assert "name" in lines[0]
    assert "Alice" in lines[1]
