"""Tests for Gmail plugin."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pytest


# Path to Gmail plugin
GMAIL_PLUGIN = Path(__file__).parent.parent / "jn_home" / "plugins" / "protocols" / "gmail_.py"


class TestGmailQueryBuilder:
    """Test Gmail query string building."""

    def test_build_gmail_query_simple(self):
        """Test building simple query."""
        # Import the function from the plugin
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import sys
sys.path.insert(0, '/home/user/jn/jn_home/plugins/protocols')
from gmail_ import build_gmail_query

params = {"from": "boss@company.com", "is": "unread"}
print(build_gmail_query(params))
""",
            ],
            capture_output=True,
            text=True,
        )

        query = result.stdout.strip()
        assert "from:boss@company.com" in query
        assert "is:unread" in query

    def test_build_gmail_query_with_list(self):
        """Test building query with list values."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import sys
sys.path.insert(0, '/home/user/jn/jn_home/plugins/protocols')
from gmail_ import build_gmail_query

params = {"from": ["user1@example.com", "user2@example.com"]}
print(build_gmail_query(params))
""",
            ],
            capture_output=True,
            text=True,
        )

        query = result.stdout.strip()
        assert "from:user1@example.com" in query
        assert "from:user2@example.com" in query

    def test_build_gmail_query_empty(self):
        """Test building query with no params."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import sys
sys.path.insert(0, '/home/user/jn/jn_home/plugins/protocols')
from gmail_ import build_gmail_query

params = {}
print(build_gmail_query(params))
""",
            ],
            capture_output=True,
            text=True,
        )

        query = result.stdout.strip()
        assert query == ""


class TestMessageParsing:
    """Test Gmail message parsing."""

    def test_parse_message_minimal(self):
        """Test parsing minimal message format."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import sys
import json
sys.path.insert(0, '/home/user/jn/jn_home/plugins/protocols')
from gmail_ import parse_message

msg = {
    "id": "12345",
    "threadId": "thread123",
    "labelIds": ["INBOX", "UNREAD"],
    "snippet": "This is a test message",
    "internalDate": "1640000000000"
}

result = parse_message(msg, format="minimal")
print(json.dumps(result))
""",
            ],
            capture_output=True,
            text=True,
        )

        record = json.loads(result.stdout)
        assert record["id"] == "12345"
        assert record["thread_id"] == "thread123"
        assert "INBOX" in record["labels"]

    def test_parse_message_with_headers(self):
        """Test parsing message with headers."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import sys
import json
sys.path.insert(0, '/home/user/jn/jn_home/plugins/protocols')
from gmail_ import parse_message

msg = {
    "id": "12345",
    "threadId": "thread123",
    "payload": {
        "headers": [
            {"name": "From", "value": "sender@example.com"},
            {"name": "To", "value": "recipient@example.com"},
            {"name": "Subject", "value": "Test Subject"}
        ]
    }
}

result = parse_message(msg, format="metadata")
print(json.dumps(result))
""",
            ],
            capture_output=True,
            text=True,
        )

        record = json.loads(result.stdout)
        assert record["from"] == "sender@example.com"
        assert record["to"] == "recipient@example.com"
        assert record["subject"] == "Test Subject"


class TestErrorRecords:
    """Test error record generation."""

    def test_error_record_format(self):
        """Test error records have correct format."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import sys
import json
sys.path.insert(0, '/home/user/jn/jn_home/plugins/protocols')
from gmail_ import error_record

err = error_record("test_error", "Test message", extra_field="value")
print(json.dumps(err))
""",
            ],
            capture_output=True,
            text=True,
        )

        record = json.loads(result.stdout)
        assert record["_error"] is True
        assert record["type"] == "test_error"
        assert record["message"] == "Test message"
        assert record["extra_field"] == "value"


class TestGmailPluginCLI:
    """Test Gmail plugin CLI interface."""

    def test_plugin_requires_mode(self):
        """Test that plugin requires --mode argument."""
        result = subprocess.run(
            [sys.executable, str(GMAIL_PLUGIN)],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "--mode is required" in result.stderr

    def test_plugin_help(self):
        """Test plugin help output."""
        result = subprocess.run(
            [sys.executable, str(GMAIL_PLUGIN), "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Gmail protocol plugin" in result.stdout
        assert "--mode" in result.stdout
        assert "--from" in result.stdout
        assert "--subject" in result.stdout


class TestGmailProfiles:
    """Test Gmail profile definitions."""

    def test_meta_json_exists(self):
        """Test _meta.json exists and is valid."""
        meta_path = Path(__file__).parent.parent / "jn_home" / "profiles" / "gmail" / "_meta.json"
        assert meta_path.exists()

        with open(meta_path) as f:
            meta = json.load(f)

        assert meta["auth_type"] == "oauth2"
        assert "sources" in meta
        assert "messages" in meta["sources"]

    def test_messages_profile_exists(self):
        """Test messages.json profile exists and is valid."""
        profile_path = (
            Path(__file__).parent.parent / "jn_home" / "profiles" / "gmail" / "messages.json"
        )
        assert profile_path.exists()

        with open(profile_path) as f:
            profile = json.load(f)

        assert profile["type"] == "source"
        assert "params" in profile
        assert "from" in profile["params"]
        assert "to" in profile["params"]
        assert "subject" in profile["params"]

    def test_inbox_profile_has_defaults(self):
        """Test inbox.json has default parameters."""
        profile_path = Path(__file__).parent.parent / "jn_home" / "profiles" / "gmail" / "inbox.json"
        assert profile_path.exists()

        with open(profile_path) as f:
            profile = json.load(f)

        assert profile["type"] == "source"
        assert "defaults" in profile
        assert profile["defaults"]["in"] == "inbox"

    def test_all_profiles_exist(self):
        """Test all declared profiles exist."""
        profiles_dir = Path(__file__).parent.parent / "jn_home" / "profiles" / "gmail"
        expected_profiles = [
            "messages.json",
            "inbox.json",
            "unread.json",
            "starred.json",
            "sent.json",
            "attachments.json",
        ]

        for profile_file in expected_profiles:
            assert (profiles_dir / profile_file).exists(), f"{profile_file} should exist"

    def test_all_profiles_valid_json(self):
        """Test all profiles are valid JSON."""
        profiles_dir = Path(__file__).parent.parent / "jn_home" / "profiles" / "gmail"

        for profile_file in profiles_dir.glob("*.json"):
            with open(profile_file) as f:
                data = json.load(f)
                assert isinstance(data, dict), f"{profile_file.name} should contain a JSON object"
