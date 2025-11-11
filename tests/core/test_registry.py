"""Tests for plugin registry pattern matching."""

from pathlib import Path

import pytest

from jn.plugins.discovery import PluginMetadata
from jn.plugins.registry import build_registry


def test_registry_match_found():
    """Test registry finds matching plugin."""
    plugins = {
        "csv_": PluginMetadata(
            name="csv_",
            path="csv_.py",
            mtime=0.0,
            matches=[r".*\.csv$", r".*\.tsv$"],
        ),
        "json_": PluginMetadata(
            name="json_",
            path="json_.py",
            mtime=0.0,
            matches=[r".*\.json$"],
        ),
    }

    registry = build_registry(plugins)

    assert registry.match("data.csv") == "csv_"
    assert registry.match("data.tsv") == "csv_"
    assert registry.match("data.json") == "json_"


def test_registry_match_not_found():
    """Test registry returns None when no plugin matches."""
    plugins = {
        "csv_": PluginMetadata(
            name="csv_",
            path="csv_.py",
            mtime=0.0,
            matches=[r".*\.csv$"],
        ),
    }

    registry = build_registry(plugins)

    # Unknown extension should return None
    result = registry.match("data.unknownext")
    assert result is None


def test_registry_longest_match_wins():
    """Test registry prefers longest matching pattern."""
    plugins = {
        "generic": PluginMetadata(
            name="generic",
            path="generic.py",
            mtime=0.0,
            matches=[r".*\.txt$"],
        ),
        "specific": PluginMetadata(
            name="specific",
            path="specific.py",
            mtime=0.0,
            matches=[r".*special.*\.txt$"],  # Longer, more specific
        ),
    }

    registry = build_registry(plugins)

    # Generic should match short pattern
    assert registry.match("file.txt") == "generic"

    # Specific should match longer pattern
    assert registry.match("special_file.txt") == "specific"


def test_registry_handles_invalid_regex():
    """Test registry skips invalid regex patterns gracefully."""
    plugins = {
        "bad_regex": PluginMetadata(
            name="bad_regex",
            path="bad.py",
            mtime=0.0,
            matches=[r"[invalid(regex"],  # Invalid regex
        ),
        "good": PluginMetadata(
            name="good",
            path="good.py",
            mtime=0.0,
            matches=[r".*\.good$"],  # Valid regex
        ),
    }

    # Should not crash, just skip invalid patterns
    registry = build_registry(plugins)

    # Good plugin should still work
    assert registry.match("file.good") == "good"

    # Bad regex plugin won't match anything (pattern was skipped)
    assert registry.match("file.bad") is None
