"""Tests for Gmail plugin.

NOTE: Gmail plugin requires OAuth2 credentials and cannot be fully tested
without a real Gmail account. These tests verify the plugin structure and
CLI interface only. Full integration testing requires manual setup.
"""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def gmail_plugin():
    """Path to Gmail plugin."""
    return Path(__file__).parent.parent.parent / "jn_home" / "plugins" / "protocols" / "gmail_.py"


def test_gmail_plugin_help(gmail_plugin):
    """Test Gmail plugin shows help."""
    result = subprocess.run(
        ["uv", "run", "--script", str(gmail_plugin), "--help"],
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result.returncode == 0
    assert "Gmail protocol plugin" in result.stdout
    assert "--mode" in result.stdout
    assert "--from" in result.stdout
    assert "--to" in result.stdout
    assert "--subject" in result.stdout


def test_gmail_plugin_requires_mode(gmail_plugin):
    """Test Gmail plugin requires --mode argument."""
    result = subprocess.run(
        ["uv", "run", "--script", str(gmail_plugin)],
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result.returncode != 0
    assert "--mode is required" in result.stderr


def test_gmail_plugin_mode_choices(gmail_plugin):
    """Test Gmail plugin only accepts 'read' mode."""
    result = subprocess.run(
        ["uv", "run", "--script", str(gmail_plugin), "--mode", "write"],
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result.returncode != 0
    assert "invalid choice" in result.stderr.lower() or "invalid choice" in result.stdout.lower()


@pytest.mark.skip(reason="Requires Gmail OAuth2 credentials - manual testing only")
def test_gmail_plugin_missing_credentials(gmail_plugin, tmp_path):
    """Test Gmail plugin error when credentials missing.

    This test is skipped by default as it requires specific test setup.
    To run manually:
      pytest tests/cli/test_gmail_plugin.py::test_gmail_plugin_missing_credentials -v
    """
    # Use non-existent credentials path
    fake_creds = tmp_path / "nonexistent-credentials.json"
    fake_token = tmp_path / "nonexistent-token.json"

    result = subprocess.run(
        [
            "uv", "run", "--script", str(gmail_plugin),
            "--mode", "read",
            "--credentials-path", str(fake_creds),
            "--token-path", str(fake_token),
        ],
        capture_output=True,
        text=True,
        timeout=30
    )

    # Should output error record (not crash)
    assert "_error" in result.stdout or "credentials" in result.stdout.lower()


# Integration tests (require real Gmail account)
# These are marked as manual-only

@pytest.mark.skip(reason="Requires real Gmail account with OAuth2 setup")
def test_gmail_plugin_real_account():
    """Integration test with real Gmail account.

    To run this test:
    1. Set up OAuth2 credentials at ~/.jn/gmail-credentials.json
    2. Run: pytest tests/cli/test_gmail_plugin.py::test_gmail_plugin_real_account -v
    3. Complete OAuth flow in browser

    Example manual test:
      uv run --script jn_home/plugins/protocols/gmail_.py \\
        --mode read \\
        --format minimal \\
        --is unread | head -n 5
    """
    pass  # Manual testing only
