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
