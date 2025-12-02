"""Tests for HTTP protocol plugin.

These tests use mocking to avoid external API dependencies.
The HTTP plugin is still Python-based (using requests library).
Zig HTTP plugin is planned for Sprint 09.
"""

import json
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

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


class MockHTTPHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for testing."""

    def log_message(self, format, *args):
        """Suppress request logging."""
        pass

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/user/1":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"id": 1, "name": "Alice"}).encode())
        elif self.path == "/users":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
                {"id": 3, "name": "Charlie"},
            ]
            self.wfile.write(json.dumps(data).encode())
        elif self.path == "/notfound":
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not Found"}).encode())
        elif self.path == "/text":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Hello, World!")
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture
def mock_server():
    """Start a local HTTP server for testing."""
    server = HTTPServer(("127.0.0.1", 0), MockHTTPHandler)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_http_plugin_fetch_json(http_plugin, mock_server):
    """Test fetching JSON object from URL."""
    url = f"{mock_server}/user/1"

    result = subprocess.run(
        ["uv", "run", "--script", str(http_plugin), "--mode", "read", url],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, f"HTTP plugin failed: {result.stderr}"

    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) >= 1, "Expected at least one NDJSON record"

    record = json.loads(lines[0])
    assert isinstance(record, dict)
    assert record["id"] == 1
    assert record["name"] == "Alice"


def test_http_plugin_fetch_json_array(http_plugin, mock_server):
    """Test fetching JSON array - should yield multiple records."""
    url = f"{mock_server}/users"

    result = subprocess.run(
        ["uv", "run", "--script", str(http_plugin), "--mode", "read", url],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, f"HTTP plugin failed: {result.stderr}"

    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) == 3, f"Expected 3 records, got {len(lines)}"

    records = [json.loads(line) for line in lines]
    assert records[0]["name"] == "Alice"
    assert records[1]["name"] == "Bob"
    assert records[2]["name"] == "Charlie"


def test_http_plugin_with_headers(http_plugin, mock_server):
    """Test HTTP plugin with custom headers."""
    url = f"{mock_server}/user/1"

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

    lines = [line for line in result.stdout.strip().split("\n") if line]
    record = json.loads(lines[0])
    assert record["id"] == 1


def test_http_plugin_404_error(http_plugin, mock_server):
    """Test HTTP plugin with 404 error - yields error record."""
    url = f"{mock_server}/notfound"

    result = subprocess.run(
        ["uv", "run", "--script", str(http_plugin), "--mode", "read", url],
        capture_output=True,
        text=True,
        timeout=10,
    )

    # Should exit successfully (errors are data, not exceptions)
    assert result.returncode == 0

    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) >= 1

    record = json.loads(lines[0])
    assert record.get("_error") is True
    assert "404" in str(record) or "Not Found" in str(record)


def test_jn_cat_http_url(invoke, mock_server):
    """Test jn cat with HTTP URL."""
    url = f"{mock_server}/user/1"

    result = invoke(["cat", url])

    assert result.exit_code == 0, f"jn cat failed: {result.output}"

    lines = [line for line in result.output.strip().split("\n") if line]
    record = json.loads(lines[0])
    assert record["id"] == 1
    assert record["name"] == "Alice"


def test_jn_run_http_to_csv(invoke, mock_server, tmp_path):
    """Test jn run with HTTP source and CSV destination."""
    url = f"{mock_server}/users"
    output = tmp_path / "users.csv"

    result = invoke(["run", url, str(output)])

    assert result.exit_code == 0, f"jn run failed: {result.output}"
    assert output.exists()

    content = output.read_text()
    assert "id" in content.lower()
    assert "name" in content.lower()
    assert "Alice" in content
    assert "Bob" in content
    assert "Charlie" in content
