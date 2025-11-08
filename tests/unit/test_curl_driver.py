"""Unit tests for curl driver (no network required)."""

from unittest.mock import Mock, patch

from jn.drivers.curl import spawn_curl


def test_spawn_curl_get_builds_correct_argv():
    """Test GET request argv construction."""
    with patch("jn.drivers.curl.subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0, stdout=b'{"result":"ok"}', stderr=b""
        )

        spawn_curl(
            method="GET", url="https://api.example.com/data", timeout=30
        )

        # Verify subprocess.run was called with correct argv
        call_args = mock_run.call_args
        argv = call_args[0][0]

        assert argv[0] == "curl"
        assert "-sS" in argv
        assert "--max-time" in argv
        assert "30" in argv
        assert "https://api.example.com/data" == argv[-1]


def test_spawn_curl_post_with_stdin():
    """Test POST with stdin body."""
    with patch("jn.drivers.curl.subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0, stdout=b"ok", stderr=b""
        )

        spawn_curl(
            method="POST",
            url="https://api.example.com/data",
            body="stdin",
            stdin=b'{"test":"data"}',
        )

        call_args = mock_run.call_args
        argv = call_args[0][0]

        assert "-X" in argv
        assert "POST" in argv
        assert "--data-binary" in argv
        assert "@-" in argv
        # Check stdin was passed
        assert call_args[1]["input"] == b'{"test":"data"}'


def test_spawn_curl_headers():
    """Test headers are added correctly."""
    with patch("jn.drivers.curl.subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0, stdout=b"ok", stderr=b""
        )

        spawn_curl(
            method="GET",
            url="https://api.example.com",
            headers={
                "Authorization": "Bearer token123",
                "Content-Type": "application/json",
            },
        )

        call_args = mock_run.call_args
        argv = call_args[0][0]

        # Headers should be in argv
        argv_str = " ".join(argv)
        assert "-H" in argv
        assert "Authorization: Bearer token123" in argv_str
        assert "Content-Type: application/json" in argv_str


def test_spawn_curl_retry_settings():
    """Test retry configuration."""
    with patch("jn.drivers.curl.subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0, stdout=b"ok", stderr=b""
        )

        spawn_curl(
            method="GET",
            url="https://api.example.com",
            retry=3,
            retry_delay=5,
        )

        call_args = mock_run.call_args
        argv = call_args[0][0]

        assert "--retry" in argv
        assert "3" in argv
        assert "--retry-delay" in argv
        assert "5" in argv


def test_spawn_curl_follow_redirects():
    """Test redirect following."""
    with patch("jn.drivers.curl.subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0, stdout=b"ok", stderr=b""
        )

        # With redirects
        spawn_curl(
            method="GET",
            url="https://api.example.com",
            follow_redirects=True,
        )
        argv_with = mock_run.call_args[0][0]
        assert "-L" in argv_with

        # Without redirects
        spawn_curl(
            method="GET",
            url="https://api.example.com",
            follow_redirects=False,
        )
        argv_without = mock_run.call_args[0][0]
        assert "-L" not in argv_without


def test_spawn_curl_fail_on_error():
    """Test fail_on_error flag."""
    with patch("jn.drivers.curl.subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0, stdout=b"ok", stderr=b""
        )

        # With fail_on_error (default)
        spawn_curl(
            method="GET", url="https://api.example.com", fail_on_error=True
        )
        argv_with = mock_run.call_args[0][0]
        assert "-f" in argv_with

        # Without fail_on_error
        spawn_curl(
            method="GET", url="https://api.example.com", fail_on_error=False
        )
        argv_without = mock_run.call_args[0][0]
        assert "-f" not in argv_without


def test_spawn_curl_returns_completed():
    """Test that Completed object is returned correctly."""
    with patch("jn.drivers.curl.subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout=b'{"status":"success"}',
            stderr=b"some warning",
        )

        result = spawn_curl(method="GET", url="https://api.example.com")

        assert result.returncode == 0
        assert result.stdout == b'{"status":"success"}'
        assert result.stderr == b"some warning"


def test_spawn_curl_handles_errors():
    """Test error responses."""
    with patch("jn.drivers.curl.subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=22,
            stdout=b"",
            stderr=b"curl: (22) The requested URL returned error: 404",
        )

        result = spawn_curl(
            method="GET", url="https://api.example.com/notfound"
        )

        assert result.returncode == 22
        assert b"404" in result.stderr


def test_spawn_curl_literal_body():
    """Test literal string body."""
    with patch("jn.drivers.curl.subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0, stdout=b"ok", stderr=b""
        )

        spawn_curl(
            method="POST",
            url="https://api.example.com",
            body="test-data-literal",
        )

        call_args = mock_run.call_args
        argv = call_args[0][0]

        assert "-d" in argv
        assert "test-data-literal" in argv


def test_spawn_curl_custom_timeout():
    """Test custom timeout value."""
    with patch("jn.drivers.curl.subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0, stdout=b"ok", stderr=b""
        )

        spawn_curl(method="GET", url="https://api.example.com", timeout=60)

        call_args = mock_run.call_args
        argv = call_args[0][0]

        assert "--max-time" in argv
        assert "60" in argv
