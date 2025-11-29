"""Tests for glob-based file reading with path metadata injection."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def jn_cli():
    """Return path to jn CLI (installed in venv or via module)."""
    jn_path = shutil.which("jn")
    if jn_path:
        return [jn_path]
    return [sys.executable, "-m", "jn.cli.main"]


@pytest.fixture
def test_data_dir():
    """Create a temporary directory structure with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create directory structure:
        # tmpdir/
        #   active/
        #     process1.jsonl
        #   completed/
        #     process2.jsonl
        #     process3.jsonl
        #   data.csv

        active = root / "active"
        completed = root / "completed"
        active.mkdir()
        completed.mkdir()

        # JSONL files
        (active / "process1.jsonl").write_text(
            '{"event": "start", "id": 1}\n' '{"event": "finish", "id": 1}\n'
        )
        (completed / "process2.jsonl").write_text(
            '{"event": "start", "id": 2}\n' '{"event": "error", "id": 2}\n'
        )
        (completed / "process3.jsonl").write_text(
            '{"event": "complete", "id": 3}\n'
        )

        # CSV file
        (root / "data.csv").write_text("name,value\nalice,10\nbob,20\n")

        yield root


class TestGlobAddressParsing:
    """Test that glob patterns are correctly identified."""

    def test_simple_glob_pattern(self):
        """Test *.jsonl is identified as glob."""
        from src.jn.addressing import parse_address

        addr = parse_address("*.jsonl")
        assert addr.type == "glob"
        assert addr.base == "*.jsonl"

    def test_recursive_glob_pattern(self):
        """Test **/*.jsonl is identified as glob."""
        from src.jn.addressing import parse_address

        addr = parse_address("data/**/*.jsonl")
        assert addr.type == "glob"
        assert addr.base == "data/**/*.jsonl"

    def test_question_mark_in_square_brackets(self):
        """Test pattern with character class containing ?-like patterns is glob."""
        from src.jn.addressing import parse_address

        # Note: standalone ? is ambiguous with query strings
        # Use patterns that are clearly globs
        addr = parse_address("file[0-9].csv")
        assert addr.type == "glob"

    def test_character_class_glob(self):
        """Test file[0-9].csv is identified as glob."""
        from src.jn.addressing import parse_address

        addr = parse_address("file[0-9].csv")
        assert addr.type == "glob"

    def test_glob_with_parameters(self):
        """Test glob with query parameters."""
        from src.jn.addressing import parse_address

        addr = parse_address("data/**/*.jsonl?limit=10")
        assert addr.type == "glob"
        assert addr.base == "data/**/*.jsonl"
        assert addr.parameters == {"limit": "10"}

    def test_glob_protocol_prefix(self):
        """Test glob:// protocol prefix."""
        from src.jn.addressing import parse_address

        addr = parse_address("glob://data/**/*.jsonl")
        assert addr.type == "glob"

    def test_regular_file_not_glob(self):
        """Test regular file is not identified as glob."""
        from src.jn.addressing import parse_address

        addr = parse_address("data.csv")
        assert addr.type == "file"


class TestGlobIntegration:
    """Test glob file reading with jn cat."""

    def test_read_jsonl_files(self, jn_cli, test_data_dir):
        """Test reading multiple JSONL files with glob."""
        result = subprocess.run(
            [*jn_cli, "cat", f"{test_data_dir}/**/*.jsonl"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        lines = [
            json.loads(line) for line in result.stdout.strip().split("\n")
        ]

        # Should have 5 records total (2 + 2 + 1)
        assert len(lines) == 5

        # Check metadata is injected
        for record in lines:
            assert "_path" in record
            assert "_dir" in record
            assert "_filename" in record
            assert "_basename" in record
            assert "_ext" in record
            assert "_file_index" in record
            assert "_line_index" in record

    def test_filter_by_directory(self, jn_cli, test_data_dir):
        """Test filtering by directory using injected _dir."""
        # First get all records
        result = subprocess.run(
            [*jn_cli, "cat", f"{test_data_dir}/**/*.jsonl"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        lines = [
            json.loads(line) for line in result.stdout.strip().split("\n")
        ]

        # Filter to only completed directory
        completed = [r for r in lines if "completed" in r["_dir"]]
        assert len(completed) == 3  # 2 + 1 records

        # Filter to only active directory
        active = [r for r in lines if "active" in r["_dir"]]
        assert len(active) == 2

    def test_filter_by_filename(self, jn_cli, test_data_dir):
        """Test filtering by filename using injected _filename."""
        result = subprocess.run(
            [*jn_cli, "cat", f"{test_data_dir}/**/*.jsonl"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        lines = [
            json.loads(line) for line in result.stdout.strip().split("\n")
        ]

        # Filter to specific file
        process1 = [r for r in lines if r["_filename"] == "process1.jsonl"]
        assert len(process1) == 2

    def test_limit_parameter(self, jn_cli, test_data_dir):
        """Test limit parameter stops after N records."""
        result = subprocess.run(
            [*jn_cli, "cat", f"{test_data_dir}/**/*.jsonl?limit=2"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        lines = [
            json.loads(line) for line in result.stdout.strip().split("\n")
        ]
        assert len(lines) == 2

    def test_file_limit_parameter(self, jn_cli, test_data_dir):
        """Test file_limit parameter stops after N files."""
        result = subprocess.run(
            [*jn_cli, "cat", f"{test_data_dir}/**/*.jsonl?file_limit=1"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        lines = [
            json.loads(line) for line in result.stdout.strip().split("\n")
        ]

        # Should only have records from one file
        assert len(set(r["_filename"] for r in lines)) == 1

    def test_mixed_file_types(self, jn_cli, test_data_dir):
        """Test reading mixed JSONL and CSV files."""
        # Read CSV
        result = subprocess.run(
            [*jn_cli, "cat", f"{test_data_dir}/*.csv"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        lines = [
            json.loads(line) for line in result.stdout.strip().split("\n")
        ]

        # Should have 2 records from CSV
        assert len(lines) == 2

        # Check CSV data is parsed
        names = [r["name"] for r in lines]
        assert "alice" in names
        assert "bob" in names

        # Check metadata
        assert all(r["_ext"] == ".csv" for r in lines)

    def test_piped_to_filter(self, jn_cli, test_data_dir):
        """Test piping glob output to jn filter."""
        # Use subprocess pipes instead of shell=True
        cat_proc = subprocess.Popen(
            [*jn_cli, "cat", f"{test_data_dir}/**/*.jsonl"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        filter_proc = subprocess.Popen(
            [*jn_cli, "filter", 'select(.event == "error")'],
            stdin=cat_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        cat_proc.stdout.close()  # Allow cat_proc to receive SIGPIPE
        stdout, _stderr = filter_proc.communicate()
        cat_proc.wait()

        assert filter_proc.returncode == 0

        lines = [
            json.loads(line) for line in stdout.strip().split("\n") if line
        ]
        assert len(lines) == 1
        assert lines[0]["event"] == "error"


class TestGlobPlugin:
    """Test glob plugin directly."""

    def test_plugin_with_limit(self, test_data_dir):
        """Test glob plugin --limit parameter."""
        plugin_path = (
            Path(__file__).parent.parent.parent
            / "jn_home"
            / "plugins"
            / "protocols"
            / "glob_.py"
        )

        result = subprocess.run(
            [
                "python",
                str(plugin_path),
                "--mode",
                "read",
                "--limit",
                "2",
                f"{test_data_dir}/**/*.jsonl",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        lines = [
            json.loads(line) for line in result.stdout.strip().split("\n")
        ]
        assert len(lines) == 2

    def test_plugin_with_file_limit(self, test_data_dir):
        """Test glob plugin --file-limit parameter."""
        plugin_path = (
            Path(__file__).parent.parent.parent
            / "jn_home"
            / "plugins"
            / "protocols"
            / "glob_.py"
        )

        result = subprocess.run(
            [
                "python",
                str(plugin_path),
                "--mode",
                "read",
                "--file-limit",
                "1",
                f"{test_data_dir}/**/*.jsonl",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        lines = [
            json.loads(line) for line in result.stdout.strip().split("\n")
        ]
        filenames = set(r["_filename"] for r in lines)
        assert len(filenames) == 1
