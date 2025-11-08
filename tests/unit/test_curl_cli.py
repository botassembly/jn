"""Unit tests for curl CLI commands."""

from jn.cli import app


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
