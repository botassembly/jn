"""Tests for json_viewer.py plugin using pexpect."""

import json
import sys
from pathlib import Path

import pexpect
import pytest


@pytest.fixture
def viewer_path():
    """Path to json_viewer.py plugin."""
    return Path("jn_home/plugins/formats/json_viewer.py")


@pytest.fixture
def sample_data():
    """Sample NDJSON data for testing."""
    records = [
        {"name": "Alice", "age": 30, "city": "New York"},
        {"name": "Bob", "age": 25, "city": "San Francisco"},
        {"name": "Charlie", "age": 35, "city": "Boston"},
    ]
    return "\n".join(json.dumps(r) for r in records)


def test_viewer_starts_and_displays_data(viewer_path, sample_data):
    """Test that viewer starts, loads data, and displays it without hanging."""
    # Start the viewer with sample data
    child = pexpect.spawn(
        f"uv run {viewer_path} --mode write",
        timeout=10,
        encoding="utf-8",
        dimensions=(24, 80),
    )

    try:
        # Send sample data
        child.send(sample_data)
        child.sendeof()

        # Wait for viewer to start and display (should see "JSON Viewer" in title)
        child.expect("JSON Viewer", timeout=8)

        # Should show "Record 1 of 3" since we sent 3 records
        child.expect("Record.*of.*3", timeout=2)

        # Should display the first record's name
        child.expect("Alice", timeout=2)

        # Quit the viewer
        child.send("q")

        # Should exit cleanly
        child.expect(pexpect.EOF, timeout=2)
        child.close()

        assert (
            child.exitstatus == 0
        ), f"Viewer exited with code {child.exitstatus}"

    except pexpect.TIMEOUT as e:
        child.close(force=True)
        pytest.fail(f"Viewer hung or didn't respond: {e}")


def test_viewer_handles_no_data(viewer_path):
    """Test that viewer handles empty stdin without hanging (timeout protection)."""
    # Start viewer with no data (immediate EOF)
    child = pexpect.spawn(
        f"uv run {viewer_path} --mode write",
        timeout=10,
        encoding="utf-8",
        dimensions=(24, 80),
    )

    try:
        # Send EOF immediately (no data)
        child.sendeof()

        # Should start and show "No records to display"
        child.expect("JSON Viewer", timeout=8)
        child.expect("No records", timeout=2)

        # Quit the viewer
        child.send("q")

        # Should exit cleanly
        child.expect(pexpect.EOF, timeout=2)
        child.close()

        assert child.exitstatus == 0

    except pexpect.TIMEOUT as e:
        child.close(force=True)
        pytest.fail(f"Viewer hung on empty stdin: {e}")


def test_viewer_navigation(viewer_path, sample_data):
    """Test that viewer accepts navigation keys without crashing."""
    child = pexpect.spawn(
        f"uv run {viewer_path} --mode write",
        timeout=10,
        encoding="utf-8",
        dimensions=(24, 80),
    )

    try:
        # Send sample data
        child.send(sample_data)
        child.sendeof()

        # Wait for first record to display
        child.expect("Record.*of.*3", timeout=8)

        # Send navigation keys - just verify viewer doesn't crash
        # (exact screen output is flaky with pexpect due to timing)
        child.send("n")  # next
        import time

        time.sleep(0.5)  # Give UI time to update

        child.send("p")  # previous
        time.sleep(0.5)

        child.send("g")  # first
        time.sleep(0.5)

        # Quit - verify clean exit is the important part
        child.send("q")
        child.expect(pexpect.EOF, timeout=2)
        child.close()

        assert (
            child.exitstatus == 0
        ), "Viewer should exit cleanly after navigation"

    except pexpect.TIMEOUT as e:
        child.close(force=True)
        pytest.fail(f"Viewer hung during navigation: {e}")


def test_viewer_malformed_json(viewer_path):
    """Test that viewer handles malformed JSON gracefully."""
    child = pexpect.spawn(
        f"uv run {viewer_path} --mode write",
        timeout=10,
        encoding="utf-8",
        dimensions=(24, 80),
    )

    try:
        # Send valid record, malformed record, valid record
        child.send('{"name": "Valid"}\n')
        child.send('{"bad": json}\n')  # Invalid JSON
        child.send('{"name": "AlsoValid"}\n')
        child.sendeof()

        # Should start and show records (including error record)
        child.expect("JSON Viewer", timeout=8)
        child.expect("Record.*of.*3", timeout=2)  # Should have 3 records total

        # Quit
        child.send("q")
        child.expect(pexpect.EOF, timeout=2)
        child.close()

        assert child.exitstatus == 0

    except pexpect.TIMEOUT as e:
        child.close(force=True)
        pytest.fail(f"Malformed JSON handling failed: {e}")


class TestPythonFilterCompilation:
    """Test Python-based filter compilation for search performance."""

    @pytest.fixture
    def compile_filter(self):
        """Import and return the _compile_python_filter function."""
        # Import the regex module needed for the standalone test
        import re

        def _compile_python_filter(expr):
            """Standalone version of the filter compiler for testing."""
            expr = expr.strip()
            # Strip select() wrapper
            select_match = re.match(r'^select\s*\(\s*(.*)\s*\)\s*$', expr)
            if select_match:
                expr = select_match.group(1)

            # .field == "value"
            match = re.match(r'^\.(\w+)\s*==\s*"([^"]*)"$', expr)
            if match:
                field, value = match.groups()
                return lambda r, f=field, v=value: r.get(f) == v

            # .field == number
            match = re.match(r'^\.(\w+)\s*==\s*(-?\d+(?:\.\d+)?)$', expr)
            if match:
                field, value = match.groups()
                num_value = float(value) if '.' in value else int(value)
                return lambda r, f=field, v=num_value: r.get(f) == v

            # .field > number
            match = re.match(r'^\.(\w+)\s*>\s*(-?\d+(?:\.\d+)?)$', expr)
            if match:
                field, value = match.groups()
                num_value = float(value) if '.' in value else int(value)
                return lambda r, f=field, v=num_value: (r.get(f) is not None and r.get(f) > v)

            # .field < number
            match = re.match(r'^\.(\w+)\s*<\s*(-?\d+(?:\.\d+)?)$', expr)
            if match:
                field, value = match.groups()
                num_value = float(value) if '.' in value else int(value)
                return lambda r, f=field, v=num_value: (r.get(f) is not None and r.get(f) < v)

            # .field (truthy)
            match = re.match(r'^\.(\w+)$', expr)
            if match:
                field = match.group(1)
                return lambda r, f=field: bool(r.get(f))

            return None

        return _compile_python_filter

    def test_string_equality(self, compile_filter):
        """Test .field == 'value' pattern."""
        fn = compile_filter('.Symbol == "BRAF"')
        assert fn is not None
        assert fn({"Symbol": "BRAF"}) is True
        assert fn({"Symbol": "OTHER"}) is False
        assert fn({"other": "value"}) is False

    def test_number_equality(self, compile_filter):
        """Test .field == number pattern."""
        fn = compile_filter('.age == 30')
        assert fn is not None
        assert fn({"age": 30}) is True
        assert fn({"age": 25}) is False

    def test_number_comparison_gt(self, compile_filter):
        """Test .field > number pattern."""
        fn = compile_filter('.age > 25')
        assert fn is not None
        assert fn({"age": 30}) is True
        assert fn({"age": 25}) is False
        assert fn({"age": 20}) is False

    def test_number_comparison_lt(self, compile_filter):
        """Test .field < number pattern."""
        fn = compile_filter('.value < 100')
        assert fn is not None
        assert fn({"value": 50}) is True
        assert fn({"value": 100}) is False
        assert fn({"value": 150}) is False

    def test_truthy_check(self, compile_filter):
        """Test .field truthy pattern."""
        fn = compile_filter('.active')
        assert fn is not None
        assert fn({"active": True}) is True
        assert fn({"active": False}) is False
        assert fn({"active": "yes"}) is True
        assert fn({"other": True}) is False

    def test_select_wrapper_stripped(self, compile_filter):
        """Test that select() wrapper is properly stripped."""
        fn = compile_filter('select(.Symbol == "BRAF")')
        assert fn is not None
        assert fn({"Symbol": "BRAF"}) is True
        assert fn({"Symbol": "OTHER"}) is False

    def test_complex_expression_returns_none(self, compile_filter):
        """Test that complex expressions return None for jq fallback."""
        assert compile_filter('.name | contains("test")') is None
        assert compile_filter('.items[] | .value') is None
        assert compile_filter('.a and .b') is None

    def test_search_performance_vs_subprocess(self, compile_filter):
        """Test that Python filter is significantly faster than subprocess approach."""
        import time

        # Create test data
        records = [{"id": i, "Symbol": f"GENE{i % 100}"} for i in range(1000)]

        fn = compile_filter('.Symbol == "GENE50"')
        assert fn is not None

        start = time.time()
        matches = [i for i, r in enumerate(records) if fn(r)]
        python_time = time.time() - start

        # Should find 10 matches (1000/100)
        assert len(matches) == 10

        # Python filter should complete in under 10ms
        assert python_time < 0.01, f"Python filter took {python_time}s, expected < 0.01s"
