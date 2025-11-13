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
    return (
        Path(__file__).parent.parent.parent
        / "jn_home"
        / "plugins"
        / "protocols"
        / "gmail_.py"
    )


def test_gmail_plugin_help(gmail_plugin):
    """Test Gmail plugin shows help."""
    result = subprocess.run(
        ["uv", "run", "--script", str(gmail_plugin), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "Gmail protocol plugin" in result.stdout
    assert "--mode" in result.stdout
    assert "--format" in result.stdout
    assert "gmail://me/messages" in result.stdout  # URL example


def test_gmail_plugin_requires_mode(gmail_plugin):
    """Test Gmail plugin requires --mode and url arguments."""
    result = subprocess.run(
        ["uv", "run", "--script", str(gmail_plugin)],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "required" in result.stderr and ("--mode" in result.stderr or "url" in result.stderr)


def test_gmail_plugin_mode_choices(gmail_plugin):
    """Test Gmail plugin only accepts 'read' mode."""
    result = subprocess.run(
        ["uv", "run", "--script", str(gmail_plugin), "--mode", "write"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert (
        "invalid choice" in result.stderr.lower()
        or "invalid choice" in result.stdout.lower()
    )


def test_gmail_plugin_url_parsing(gmail_plugin, tmp_path):
    """Test Gmail plugin requires URL argument and parses it."""
    fake_creds = tmp_path / "fake-credentials.json"
    fake_token = tmp_path / "fake-token.json"

    result = subprocess.run(
        [
            "uv",
            "run",
            "--script",
            str(gmail_plugin),
            "--mode",
            "read",
            "gmail://me/messages?is=unread",
            "--credentials-path",
            str(fake_creds),
            "--token-path",
            str(fake_token),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Should error because credentials don't exist, but proves URL was parsed
    assert "_error" in result.stdout
    assert "credentials" in result.stdout.lower()
