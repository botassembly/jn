"""Tests for HTTP protocol plugin."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def http_plugin():
    """Path to HTTP plugin."""
    return (
        Path(__file__).parent.parent.parent
        / "jn_home"
        / "plugins"
        / "protocols"
        / "http_.py"
    )


def test_http_plugin_fetch_json(http_plugin):
    """Test fetching JSON from a public URL."""
    # Use JSONPlaceholder - a free fake API for testing
    url = "https://jsonplaceholder.typicode.com/users/1"

    result = subprocess.run(
        ["uv", "run", "--script", str(http_plugin), "--mode", "read", url],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, f"HTTP plugin failed: {result.stderr}"

    # Parse output
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) >= 1, "Expected at least one NDJSON record"

    # First line should be valid JSON
    record = json.loads(lines[0])
    assert isinstance(record, dict)
    assert "id" in record
    assert record["id"] == 1


def test_http_plugin_fetch_json_array(http_plugin):
    """Test fetching JSON array - should yield multiple records."""
    # JSONPlaceholder returns an array
    url = "https://jsonplaceholder.typicode.com/users?_limit=3"

    result = subprocess.run(
        ["uv", "run", "--script", str(http_plugin), "--mode", "read", url],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, f"HTTP plugin failed: {result.stderr}"

    # Parse output - should have 3 records
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) == 3, f"Expected 3 records, got {len(lines)}"

    # Each line should be valid JSON
    for line in lines:
        record = json.loads(line)
        assert isinstance(record, dict)
        assert "id" in record


def test_http_plugin_with_headers(http_plugin):
    """Test HTTP plugin with custom headers."""
    url = "https://jsonplaceholder.typicode.com/users/1"

    result = subprocess.run(
        [
            "uv",
            "run",
            "--script",
            str(http_plugin),
            "--mode",
            "read",
            "--headers",
            '{"Accept": "application/json"}',
            url,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, f"HTTP plugin failed: {result.stderr}"

    # Should still get valid JSON
    lines = [line for line in result.stdout.strip().split("\n") if line]
    record = json.loads(lines[0])
    assert "id" in record


def test_http_plugin_timeout(http_plugin):
    """Test HTTP plugin with very short timeout - yields error record."""
    url = "https://httpbin.org/delay/10"  # Delays response by 10 seconds

    result = subprocess.run(
        [
            "uv",
            "run",
            "--script",
            str(http_plugin),
            "--mode",
            "read",
            "--timeout",
            "1",  # 1 second timeout
            url,
        ],
        capture_output=True,
        text=True,
        timeout=5,  # Overall test timeout
    )

    # Should exit successfully (errors are data, not exceptions)
    assert result.returncode == 0
    # Should yield error record
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) >= 1
    record = json.loads(lines[0])
    assert record.get("_error") is True
    # Could be timeout or 503 (httpbin.org sometimes returns 503 instead of delaying)
    assert (
        "timeout" in result.stdout.lower()
        or "timed out" in result.stdout.lower()
        or "503" in result.stdout
        or "unavailable" in result.stdout.lower()
    )


def test_http_plugin_404_error(http_plugin):
    """Test HTTP plugin with 404 error - yields error record."""
    url = "https://jsonplaceholder.typicode.com/users/999999999"

    result = subprocess.run(
        ["uv", "run", "--script", str(http_plugin), "--mode", "read", url],
        capture_output=True,
        text=True,
        timeout=10,
    )

    # Should exit successfully (errors are data now, not exceptions)
    assert result.returncode == 0
    # Should yield error record
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record.get("_error") is True
    assert "404" in str(record) or "Not Found" in str(record)


def test_jn_cat_http_url(invoke):
    """Test jn cat with HTTP URL."""
    url = "https://jsonplaceholder.typicode.com/users/1"

    result = invoke(["cat", url])

    assert result.exit_code == 0, f"jn cat failed: {result.output}"

    # Parse output
    lines = [line for line in result.output.strip().split("\n") if line]
    record = json.loads(lines[0])
    assert "id" in record
    assert record["id"] == 1


def test_jn_run_http_to_csv(invoke, tmp_path):
    """Test jn run with HTTP source and CSV destination."""
    url = "https://jsonplaceholder.typicode.com/users?_limit=3"
    output = tmp_path / "users.csv"

    result = invoke(["run", url, str(output)])

    assert result.exit_code == 0, f"jn run failed: {result.output}"
    assert output.exists()

    # Check CSV content
    content = output.read_text()
    assert "id" in content.lower()
    assert "name" in content.lower()
