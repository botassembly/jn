"""Integration tests for Zig JSONL binary plugin."""

import json
import subprocess
from pathlib import Path

import pytest

# Path to the Zig JSONL binary
JSONL_BINARY = Path("plugins/zig/jsonl/bin/jsonl")


@pytest.fixture(autouse=True)
def require_binary():
    """Skip tests if binary not built."""
    if not JSONL_BINARY.exists():
        pytest.skip("Zig JSONL binary not built (run: make zig-plugins)")


class TestJnMeta:
    """Test --jn-meta metadata output."""

    def test_outputs_valid_json(self):
        """--jn-meta should output valid JSON."""
        result = subprocess.run(
            [str(JSONL_BINARY), "--jn-meta"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        meta = json.loads(result.stdout)
        assert isinstance(meta, dict)

    def test_contains_required_fields(self):
        """Metadata should contain required fields."""
        result = subprocess.run(
            [str(JSONL_BINARY), "--jn-meta"],
            capture_output=True,
            text=True,
        )
        meta = json.loads(result.stdout)
        assert meta["name"] == "jsonl"
        assert "matches" in meta
        assert "role" in meta
        assert meta["role"] == "format"

    def test_matches_jsonl_extensions(self):
        """Should match .jsonl and .ndjson files."""
        result = subprocess.run(
            [str(JSONL_BINARY), "--jn-meta"],
            capture_output=True,
            text=True,
        )
        meta = json.loads(result.stdout)
        matches = meta["matches"]
        # Should match .jsonl and .ndjson
        assert any(".jsonl" in m for m in matches)
        assert any(".ndjson" in m for m in matches)


class TestReadMode:
    """Test --mode=read for NDJSON passthrough."""

    def test_single_record(self):
        """Should pass through a single JSON record."""
        input_data = '{"name": "Alice", "age": 30}\n'
        result = subprocess.run(
            [str(JSONL_BINARY), "--mode=read"],
            input=input_data,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        output = result.stdout.strip()
        record = json.loads(output)
        assert record["name"] == "Alice"
        assert record["age"] == 30

    def test_multiple_records(self):
        """Should pass through multiple JSON records."""
        input_data = '{"id": 1}\n{"id": 2}\n{"id": 3}\n'
        result = subprocess.run(
            [str(JSONL_BINARY), "--mode=read"],
            input=input_data,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[0])["id"] == 1
        assert json.loads(lines[1])["id"] == 2
        assert json.loads(lines[2])["id"] == 3

    def test_empty_input(self):
        """Should handle empty input gracefully."""
        result = subprocess.run(
            [str(JSONL_BINARY), "--mode=read"],
            input="",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == ""

    def test_skips_empty_lines(self):
        """Should skip empty lines in input."""
        input_data = '{"id": 1}\n\n{"id": 2}\n'
        result = subprocess.run(
            [str(JSONL_BINARY), "--mode=read"],
            input=input_data,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 2


class TestWriteMode:
    """Test --mode=write for NDJSON passthrough."""

    def test_write_passthrough(self):
        """Write mode should pass through NDJSON unchanged."""
        input_data = '{"name": "Bob"}\n{"name": "Carol"}\n'
        result = subprocess.run(
            [str(JSONL_BINARY), "--mode=write"],
            input=input_data,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["name"] == "Bob"
        assert json.loads(lines[1])["name"] == "Carol"


class TestDiscovery:
    """Test plugin discovery integration."""

    def test_binary_plugin_discoverable(self):
        """Binary plugin should be discoverable via discovery module."""
        from src.jn.plugins.discovery import discover_binary_plugins

        plugins = discover_binary_plugins(Path("plugins"))
        assert "jsonl" in plugins
        meta = plugins["jsonl"]
        assert meta.is_binary is True
        assert meta.role == "format"
        assert any(".jsonl" in m for m in meta.matches)
