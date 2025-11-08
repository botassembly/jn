"""Unit tests for curl CLI commands."""

from jn.cli import app


def test_curl_source_header_parsing_valid(runner, tmp_path):
    """Test valid header parsing in curl source command."""
    jn_path = tmp_path / "jn.json"

    # Init config
    result = runner.invoke(app, ["init", "--jn", str(jn_path), "--force"])
    assert result.exit_code == 0

    # Create source with headers
    result = runner.invoke(
        app,
        [
            "new",
            "source",
            "curl",
            "test-source",
            "--url",
            "https://example.com",
            "--header",
            "Authorization: Bearer token123",
            "--header",
            "Content-Type: application/json",
            "--jn",
            str(jn_path),
        ],
    )

    assert result.exit_code == 0
    assert "Created source 'test-source'" in result.output


def test_curl_source_header_parsing_invalid(runner, tmp_path):
    """Test invalid header format is rejected."""
    jn_path = tmp_path / "jn.json"

    # Init config
    result = runner.invoke(app, ["init", "--jn", str(jn_path), "--force"])
    assert result.exit_code == 0

    # Create source with invalid header (missing colon-space)
    result = runner.invoke(
        app,
        [
            "new",
            "source",
            "curl",
            "test-source",
            "--url",
            "https://example.com",
            "--header",
            "InvalidHeader",  # No ": " separator
            "--jn",
            str(jn_path),
        ],
    )

    assert result.exit_code == 1
    assert "Invalid header format" in result.output


def test_curl_target_header_parsing_valid(runner, tmp_path):
    """Test valid header parsing in curl target command."""
    jn_path = tmp_path / "jn.json"

    # Init config
    result = runner.invoke(app, ["init", "--jn", str(jn_path), "--force"])
    assert result.exit_code == 0

    # Create target with headers
    result = runner.invoke(
        app,
        [
            "new",
            "target",
            "curl",
            "test-target",
            "--url",
            "https://example.com/webhook",
            "--header",
            "X-API-Key: secret123",
            "--header",
            "User-Agent: jn/0.1",
            "--jn",
            str(jn_path),
        ],
    )

    assert result.exit_code == 0
    assert "Created target 'test-target'" in result.output


def test_curl_source_all_options(runner, tmp_path):
    """Test curl source with all options."""
    jn_path = tmp_path / "jn.json"

    # Init config
    result = runner.invoke(app, ["init", "--jn", str(jn_path), "--force"])
    assert result.exit_code == 0

    # Create source with all options
    result = runner.invoke(
        app,
        [
            "new",
            "source",
            "curl",
            "comprehensive",
            "--url",
            "https://api.example.com/data",
            "--method",
            "POST",
            "--header",
            "Authorization: Bearer xyz",
            "--timeout",
            "60",
            "--retry",
            "5",
            "--retry-delay",
            "3",
            "--no-follow-redirects",
            "--allow-errors",
            "--jn",
            str(jn_path),
        ],
    )

    assert result.exit_code == 0

    # Verify config was saved correctly
    import json
    config = json.loads(jn_path.read_text())
    source = config["sources"][0]

    assert source["name"] == "comprehensive"
    assert source["curl"]["url"] == "https://api.example.com/data"
    assert source["curl"]["method"] == "POST"
    assert source["curl"]["headers"]["Authorization"] == "Bearer xyz"
    assert source["curl"]["timeout"] == 60
    assert source["curl"]["retry"] == 5
    assert source["curl"]["retry_delay"] == 3
    assert source["curl"]["follow_redirects"] is False
    assert source["curl"]["fail_on_error"] is False


def test_curl_target_defaults(runner, tmp_path):
    """Test curl target defaults (POST, body=stdin)."""
    jn_path = tmp_path / "jn.json"

    # Init config
    result = runner.invoke(app, ["init", "--jn", str(jn_path), "--force"])
    assert result.exit_code == 0

    # Create minimal target
    result = runner.invoke(
        app,
        [
            "new",
            "target",
            "curl",
            "webhook",
            "--url",
            "https://webhook.site/abc123",
            "--jn",
            str(jn_path),
        ],
    )

    assert result.exit_code == 0

    # Verify defaults
    import json
    config = json.loads(jn_path.read_text())
    target = config["targets"][0]

    assert target["curl"]["method"] == "POST"  # Default for targets
    assert target["curl"]["body"] == "stdin"  # Automatically set
    assert target["curl"]["timeout"] == 30  # Default
    assert target["curl"]["retry"] == 0  # Default (no retry)
    assert target["curl"]["follow_redirects"] is True  # Default
    assert target["curl"]["fail_on_error"] is True  # Default
