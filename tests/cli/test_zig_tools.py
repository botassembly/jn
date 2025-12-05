"""Integration tests for Zig CLI tools.

These tests verify the Zig implementations of JN tools work correctly
by invoking the binaries directly with subprocess.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest


# Path to Zig tool binaries
TOOLS_DIR = Path(__file__).parent.parent.parent / "tools" / "zig"


def get_tool_path(name: str) -> Path:
    """Get path to a Zig tool binary."""
    return TOOLS_DIR / name / "bin" / name


def run_tool(name: str, args: list = None, input_data: str = None, env: dict = None) -> tuple:
    """Run a Zig tool and return (returncode, stdout, stderr)."""
    tool_path = get_tool_path(name)
    if not tool_path.exists():
        pytest.skip(f"Tool {name} not built (run 'make zig-tools')")

    cmd = [str(tool_path)] + (args or [])
    run_env = os.environ.copy()
    # Ensure JN_HOME is set for tool discovery (e.g., zq)
    if "JN_HOME" not in run_env:
        run_env["JN_HOME"] = str(Path(__file__).parent.parent.parent / "jn_home")
    if env:
        run_env.update(env)

    result = subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
        text=True,
        env=run_env,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.fixture
def csv_file(tmp_path):
    """Create a test CSV file."""
    path = tmp_path / "test.csv"
    path.write_text("name,age,city\nAlice,30,NYC\nBob,25,LA\nCarol,35,SF\n")
    return path


@pytest.fixture
def json_file(tmp_path):
    """Create a test JSON array file."""
    path = tmp_path / "test.json"
    data = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
        {"name": "Carol", "age": 35},
    ]
    path.write_text(json.dumps(data))
    return path


@pytest.fixture
def ndjson_data():
    """Sample NDJSON data."""
    return '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n{"name":"Carol","age":35}\n'


# =============================================================================
# jn-cat tests
# =============================================================================

class TestJnCat:
    """Tests for jn-cat universal reader."""

    def test_cat_csv_to_ndjson(self, csv_file):
        """jn-cat should convert CSV to NDJSON."""
        code, stdout, stderr = run_tool("jn-cat", [str(csv_file)])
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l]
        assert len(lines) == 3

        first = json.loads(lines[0])
        assert first["name"] == "Alice"
        assert first["age"] == "30"  # CSV values are strings

    def test_cat_json_to_ndjson(self, json_file):
        """jn-cat should convert JSON array to NDJSON."""
        code, stdout, stderr = run_tool("jn-cat", [str(json_file)])
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l]
        assert len(lines) == 3

        first = json.loads(lines[0])
        assert first["name"] == "Alice"
        assert first["age"] == 30  # JSON preserves types

    def test_cat_format_override(self, tmp_path):
        """jn-cat should respect format override (~csv)."""
        path = tmp_path / "data.txt"
        path.write_text("name,age\nAlice,30\n")

        code, stdout, stderr = run_tool("jn-cat", [f"{path}~csv"])
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l]
        assert len(lines) == 1
        assert json.loads(lines[0])["name"] == "Alice"

    def test_cat_help(self):
        """jn-cat --help should show usage."""
        code, stdout, stderr = run_tool("jn-cat", ["--help"])
        assert code == 0
        assert "jn-cat" in stdout or "USAGE" in stdout

    def test_cat_file_not_found(self):
        """jn-cat should report error for missing file."""
        code, stdout, stderr = run_tool("jn-cat", ["/nonexistent/file.csv"])
        assert code != 0
        # Error message in stdout or stderr
        assert "error" in (stdout + stderr).lower() or "not found" in (stdout + stderr).lower()


# =============================================================================
# jn-put tests
# =============================================================================

class TestJnPut:
    """Tests for jn-put universal writer."""

    def test_put_ndjson_to_json(self, tmp_path, ndjson_data):
        """jn-put should convert NDJSON to JSON array."""
        out_file = tmp_path / "out.json"

        code, stdout, stderr = run_tool("jn-put", [str(out_file)], input_data=ndjson_data)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        data = json.loads(out_file.read_text())
        assert isinstance(data, list)
        assert len(data) == 3
        assert data[0]["name"] == "Alice"

    def test_put_ndjson_to_csv(self, tmp_path, ndjson_data):
        """jn-put should convert NDJSON to CSV."""
        out_file = tmp_path / "out.csv"

        code, stdout, stderr = run_tool("jn-put", [str(out_file)], input_data=ndjson_data)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        content = out_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 4  # header + 3 rows
        assert "name" in lines[0]
        assert "Alice" in lines[1]

    def test_put_help(self):
        """jn-put --help should show usage."""
        code, stdout, stderr = run_tool("jn-put", ["--help"])
        assert code == 0
        assert "jn-put" in stdout or "USAGE" in stdout


# =============================================================================
# jn-filter tests
# =============================================================================

class TestJnFilter:
    """Tests for jn-filter ZQ wrapper."""

    def test_filter_select_field(self, ndjson_data):
        """jn-filter should extract field values."""
        code, stdout, stderr = run_tool("jn-filter", [".name"], input_data=ndjson_data)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l]
        assert len(lines) == 3
        assert '"Alice"' in lines[0]

    def test_filter_condition(self, ndjson_data):
        """jn-filter should filter records."""
        # ZQ uses select() for filtering
        code, stdout, stderr = run_tool("jn-filter", ["select(.age > 26)"], input_data=ndjson_data)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l]
        assert len(lines) == 2  # Alice (30) and Carol (35)

    def test_filter_help(self):
        """jn-filter --help should show usage."""
        code, stdout, stderr = run_tool("jn-filter", ["--help"])
        assert code == 0
        assert "jn-filter" in stdout or "USAGE" in stdout


# =============================================================================
# jn-head tests
# =============================================================================

class TestJnHead:
    """Tests for jn-head stream truncation."""

    def test_head_default(self, ndjson_data):
        """jn-head should return first 10 records by default."""
        # Use 3 records, should return all
        code, stdout, stderr = run_tool("jn-head", [], input_data=ndjson_data)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l]
        assert len(lines) == 3  # All 3 records (< 10)

    def test_head_limit(self, ndjson_data):
        """jn-head --lines should limit records."""
        code, stdout, stderr = run_tool("jn-head", ["--lines=2"], input_data=ndjson_data)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l]
        assert len(lines) == 2
        assert json.loads(lines[0])["name"] == "Alice"
        assert json.loads(lines[1])["name"] == "Bob"

    def test_head_help(self):
        """jn-head --help should show usage."""
        code, stdout, stderr = run_tool("jn-head", ["--help"])
        assert code == 0
        assert "jn-head" in stdout or "USAGE" in stdout


# =============================================================================
# jn-tail tests
# =============================================================================

class TestJnTail:
    """Tests for jn-tail stream truncation."""

    def test_tail_default(self, ndjson_data):
        """jn-tail should return last 10 records by default."""
        code, stdout, stderr = run_tool("jn-tail", [], input_data=ndjson_data)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l]
        assert len(lines) == 3  # All 3 records (< 10)

    def test_tail_limit(self, ndjson_data):
        """jn-tail --lines should limit to last N records."""
        code, stdout, stderr = run_tool("jn-tail", ["--lines=2"], input_data=ndjson_data)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l]
        assert len(lines) == 2
        # Should be last 2: Bob and Carol
        assert json.loads(lines[0])["name"] == "Bob"
        assert json.loads(lines[1])["name"] == "Carol"

    def test_tail_help(self):
        """jn-tail --help should show usage."""
        code, stdout, stderr = run_tool("jn-tail", ["--help"])
        assert code == 0
        assert "jn-tail" in stdout or "USAGE" in stdout


# =============================================================================
# jn-analyze tests
# =============================================================================

class TestJnAnalyze:
    """Tests for jn-analyze statistics tool."""

    def test_analyze_basic(self, ndjson_data):
        """jn-analyze should produce statistics."""
        code, stdout, stderr = run_tool("jn-analyze", [], input_data=ndjson_data)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        # Should contain record count and field info
        assert "3" in stdout  # 3 records
        assert "name" in stdout or "age" in stdout

    def test_analyze_json_output(self, ndjson_data):
        """jn-analyze --format=json should output JSON."""
        code, stdout, stderr = run_tool("jn-analyze", ["--format=json"], input_data=ndjson_data)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        data = json.loads(stdout)
        assert "record_count" in data or "records" in data or "count" in data

    def test_analyze_help(self):
        """jn-analyze --help should show usage."""
        code, stdout, stderr = run_tool("jn-analyze", ["--help"])
        assert code == 0
        assert "jn-analyze" in stdout or "USAGE" in stdout


# =============================================================================
# jn-join tests
# =============================================================================

class TestJnJoin:
    """Tests for jn-join hash join tool."""

    def test_join_basic(self, tmp_path):
        """jn-join should perform hash join."""
        # Left: users with ids
        left = tmp_path / "users.jsonl"
        left.write_text('{"id":1,"name":"Alice"}\n{"id":2,"name":"Bob"}\n')

        # Right: orders with user_id
        right = tmp_path / "orders.jsonl"
        right.write_text('{"user_id":1,"product":"Book"}\n{"user_id":2,"product":"Pen"}\n')

        code, stdout, stderr = run_tool(
            "jn-join",
            ["--left-key=id", "--right-key=user_id", str(right)],
            input_data=left.read_text()
        )
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l]
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["name"] == "Alice"
        assert first["product"] == "Book"

    def test_join_help(self):
        """jn-join --help should show usage."""
        code, stdout, stderr = run_tool("jn-join", ["--help"])
        assert code == 0
        assert "jn-join" in stdout or "USAGE" in stdout


# =============================================================================
# jn-merge tests
# =============================================================================

class TestJnMerge:
    """Tests for jn-merge source concatenation."""

    def test_merge_basic(self, tmp_path):
        """jn-merge should concatenate sources with metadata."""
        file1 = tmp_path / "a.jsonl"
        file1.write_text('{"x":1}\n')

        file2 = tmp_path / "b.jsonl"
        file2.write_text('{"x":2}\n')

        code, stdout, stderr = run_tool("jn-merge", [str(file1), str(file2)])
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l]
        assert len(lines) == 2

        # Records should have _source metadata
        first = json.loads(lines[0])
        assert first["x"] == 1
        # _source may contain filename or index

    def test_merge_no_source(self, tmp_path):
        """jn-merge --no-source should skip metadata."""
        file1 = tmp_path / "a.jsonl"
        file1.write_text('{"x":1}\n')

        file2 = tmp_path / "b.jsonl"
        file2.write_text('{"x":2}\n')

        code, stdout, stderr = run_tool("jn-merge", ["--no-source", str(file1), str(file2)])
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l]
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert "_source" not in first

    def test_merge_help(self):
        """jn-merge --help should show usage."""
        code, stdout, stderr = run_tool("jn-merge", ["--help"])
        assert code == 0
        assert "jn-merge" in stdout or "USAGE" in stdout


# =============================================================================
# jn orchestrator tests
# =============================================================================

class TestJnOrchestrator:
    """Tests for jn command dispatcher."""

    def test_jn_version(self):
        """jn --version should report version."""
        code, stdout, stderr = run_tool("jn", ["--version"])
        assert code == 0
        assert "jn" in stdout.lower() or "0." in stdout

    def test_jn_help(self):
        """jn --help should show all commands."""
        code, stdout, stderr = run_tool("jn", ["--help"])
        assert code == 0
        output = stdout + stderr
        # Should list subcommands
        assert "cat" in output
        assert "put" in output or "filter" in output

    def test_jn_unknown_command(self):
        """jn with unknown command should show error."""
        code, stdout, stderr = run_tool("jn", ["unknowncommand"])
        assert code != 0
        output = stdout + stderr
        assert "error" in output.lower() or "unknown" in output.lower()


# =============================================================================
# Pipeline tests (end-to-end)
# =============================================================================

class TestPipelines:
    """End-to-end pipeline tests."""

    def test_cat_head_pipeline(self, csv_file):
        """Test: jn-cat file.csv | jn-head --lines=2"""
        # First run cat
        code, stdout, _ = run_tool("jn-cat", [str(csv_file)])
        assert code == 0

        # Pipe to head
        code, stdout, stderr = run_tool("jn-head", ["--lines=2"], input_data=stdout)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l]
        assert len(lines) == 2

    def test_cat_filter_pipeline(self, csv_file):
        """Test: jn-cat file.csv | jn-filter 'select(.age > "28")'"""
        # First run cat
        code, stdout, _ = run_tool("jn-cat", [str(csv_file)])
        assert code == 0

        # Pipe to filter (CSV values are strings, use string comparison)
        # ZQ uses select() for filtering
        code, stdout, stderr = run_tool("jn-filter", ['select(.age > "28")'], input_data=stdout)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l]
        # Alice (30), Bob (25 - no match), Carol (35) - string comparison: "30" > "28", "35" > "28"
        assert len(lines) >= 1

    def test_cat_put_roundtrip(self, tmp_path, csv_file):
        """Test: CSV → NDJSON → JSON → NDJSON roundtrip."""
        # CSV to NDJSON
        code, stdout, _ = run_tool("jn-cat", [str(csv_file)])
        assert code == 0
        ndjson1 = stdout

        # NDJSON to JSON
        json_file = tmp_path / "out.json"
        code, _, stderr = run_tool("jn-put", [str(json_file)], input_data=ndjson1)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        # JSON back to NDJSON
        code, stdout, _ = run_tool("jn-cat", [str(json_file)])
        assert code == 0

        # Verify data preserved
        lines = [l for l in stdout.strip().split("\n") if l]
        assert len(lines) == 3
        assert json.loads(lines[0])["name"] == "Alice"
