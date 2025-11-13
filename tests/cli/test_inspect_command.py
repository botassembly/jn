"""Integration tests for jn inspect command."""

import json

import pytest


def test_inspect_with_profile_reference(invoke):
    """Test jn inspect with profile reference (@biomcp)."""
    # This will fail if MCP server not available, but tests CLI integration
    res = invoke(["inspect", "@biomcp", "--format", "json"])

    # Could fail due to missing server, but should at least attempt execution
    # Check that command runs and produces output or error
    assert res.output  # Should have some output


def test_inspect_missing_server_argument(invoke):
    """Test that inspect requires server argument."""
    res = invoke(["inspect"])

    assert res.exit_code != 0
    assert "Missing argument" in res.output or "Error" in res.output


def test_inspect_invalid_format_option(invoke):
    """Test that inspect validates format option."""
    res = invoke(["inspect", "@biomcp", "--format", "invalid"])

    assert res.exit_code != 0
    # Click should reject invalid choice
    assert "Invalid value" in res.output or "invalid" in res.output.lower()


def test_inspect_json_format_option(invoke):
    """Test that inspect accepts json format."""
    # Even if server fails, should accept the format option
    res = invoke(["inspect", "@biomcp", "--format", "json"])

    # Exit code might be non-zero if server unavailable, but format should be accepted
    # Just verify it doesn't complain about the format option
    assert "Invalid value" not in res.output


def test_inspect_text_format_option(invoke):
    """Test that inspect accepts text format (default)."""
    # Even if server fails, should accept the format option
    res = invoke(["inspect", "@biomcp", "--format", "text"])

    # Exit code might be non-zero if server unavailable, but format should be accepted
    # Just verify it doesn't complain about the format option
    assert "Invalid value" not in res.output


def test_inspect_default_format_is_text(invoke):
    """Test that inspect defaults to text format."""
    # Test without --format flag (should default to text)
    res = invoke(["inspect", "@biomcp"])

    # Should run (even if fails on missing server)
    # Text format doesn't output JSON at top level
    # If output exists and is not empty, verify it's not JSON
    if res.output.strip() and not res.output.strip().startswith("Error"):
        # Text format output should not be valid JSON
        try:
            json.loads(res.output.strip())
            # If it parses as JSON, that's wrong for text format
            pytest.fail("Default output should be text format, not JSON")
        except json.JSONDecodeError:
            # Good - text format should not be valid JSON
            pass


def test_inspect_naked_uri_syntax_accepted(invoke):
    """Test that inspect accepts naked MCP URI syntax."""
    # Test with naked URI (will fail on missing server, but tests CLI parsing)
    res = invoke(
        ["inspect", "mcp+uvx://biomcp-python/biomcp", "--format", "json"]
    )

    # Should attempt to parse and execute (even if server not available)
    # Verify no syntax errors in parsing the URI
    assert "Invalid address syntax" not in res.output


def test_inspect_profile_syntax_accepted(invoke):
    """Test that inspect accepts profile reference syntax."""
    # Test with profile reference
    res = invoke(["inspect", "@biomcp", "--format", "json"])

    # Should attempt to parse and execute
    # Verify no syntax errors
    assert "Invalid address syntax" not in res.output


def test_inspect_command_registered(invoke):
    """Test that inspect command is registered in CLI."""
    # Run jn --help and verify inspect is listed
    res = invoke(["--help"])

    assert res.exit_code == 0
    assert "inspect" in res.output.lower()


def test_inspect_help_text(invoke):
    """Test that inspect command has help text."""
    res = invoke(["inspect", "--help"])

    assert res.exit_code == 0
    assert "inspect" in res.output.lower()
    assert "server" in res.output.lower()
    assert "--format" in res.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
