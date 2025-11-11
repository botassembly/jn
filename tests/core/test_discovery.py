"""Tests for plugin discovery edge cases."""

from pathlib import Path

import pytest

from jn.plugins.discovery import discover_plugins, get_cached_plugins


def test_discovery_no_cache(tmp_path):
    """Test discovery works without cache (cache_path=None)."""
    # Create a simple plugin
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    plugin = plugin_dir / "test.py"
    plugin.write_text("""#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = [".*\\.test$"]
# ///

def reads(config=None):
    pass
""")

    # Should work with cache_path=None
    plugins = get_cached_plugins(plugin_dir, cache_path=None)
    assert "test" in plugins
    assert len(plugins["test"].matches) == 1


def test_discovery_handles_binary_file(tmp_path):
    """Test discovery handles binary/unreadable files gracefully."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    # Create a binary file that can't be decoded as UTF-8
    binary_file = plugin_dir / "binary.py"
    binary_file.write_bytes(b'\xff\xfe\x00\x01')  # Invalid UTF-8

    # Create a valid plugin
    valid_plugin = plugin_dir / "valid.py"
    valid_plugin.write_text("""#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = [".*\\.valid$"]
# ///

def reads(config=None):
    pass
""")

    # Should handle binary file gracefully (includes it with empty metadata)
    plugins = discover_plugins(plugin_dir)
    assert "valid" in plugins
    # binary is included but with empty metadata (OSError/UnicodeDecodeError caught)
    # This is expected behavior - discovery is permissive


def test_discovery_skips_test_files(tmp_path):
    """Test discovery skips test_ files."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    # Create a test file
    test_file = plugin_dir / "test_something.py"
    test_file.write_text("""#!/usr/bin/env python3
# /// script
# [tool.jn]
# matches = [".*\\.test$"]
# ///

def reads(config=None):
    pass
""")

    plugins = discover_plugins(plugin_dir)
    assert "test_something" not in plugins


def test_discovery_skips_pycache(tmp_path):
    """Test discovery skips __pycache__ files."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    # Create __pycache__ directory
    pycache = plugin_dir / "__pycache__"
    pycache.mkdir()
    (pycache / "something.pyc").write_bytes(b"compiled")

    plugins = discover_plugins(plugin_dir)
    # Should not crash and should be empty
    assert len(plugins) == 0


def test_discovery_includes_file_without_pep723(tmp_path):
    """Test discovery includes files without PEP 723 metadata (with empty matches)."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    # Create a Python file without PEP 723 block
    no_metadata = plugin_dir / "plain.py"
    no_metadata.write_text("""#!/usr/bin/env python3
def reads(config=None):
    pass
""")

    plugins = discover_plugins(plugin_dir)
    # Discovery is permissive - includes plugins even without PEP 723
    assert "plain" in plugins
    # Should have empty matches since no metadata found
    assert plugins["plain"].matches == []


def test_discovery_handles_corrupt_toml(tmp_path):
    """Test discovery handles corrupt TOML in PEP 723 block gracefully."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    # Create plugin with invalid TOML
    corrupt = plugin_dir / "corrupt.py"
    corrupt.write_text("""#!/usr/bin/env python3
# /// script
# this is not valid toml [[[
# ///

def reads(config=None):
    pass
""")

    # Should handle corrupt TOML gracefully (includes with empty metadata)
    plugins = discover_plugins(plugin_dir)
    assert "corrupt" in plugins
    # Should have empty matches since TOML parsing failed
    assert plugins["corrupt"].matches == []


def test_discovery_cache_hit(tmp_path):
    """Test discovery uses cache when file unchanged."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    cache_path = tmp_path / "cache.json"

    # Create plugin
    plugin = plugin_dir / "test.py"
    plugin.write_text("""#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = [".*\\.test$"]
# ///

def reads(config=None):
    pass
""")

    # First call - cache miss
    plugins1 = get_cached_plugins(plugin_dir, cache_path)
    assert "test" in plugins1

    # Second call - cache hit (file unchanged)
    plugins2 = get_cached_plugins(plugin_dir, cache_path)
    assert "test" in plugins2

    # Cache file should exist
    assert cache_path.exists()
