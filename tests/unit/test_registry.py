"""Tests for plugin registry system."""

import tempfile
from pathlib import Path
import pytest

from jn.registry import (
    PluginRegistry,
    RegistryEntry,
    resolve_plugin,
)


def test_registry_initialization():
    """Test registry initializes with defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / 'registry.json'
        registry = PluginRegistry(registry_path=registry_path)

        # Should have some default entries
        assert len(registry.entries) > 0

        # Check for common extensions
        csv_plugin = registry.get_plugin_for_extension('.csv')
        assert csv_plugin == 'csv_reader'

        json_plugin = registry.get_plugin_for_extension('.json')
        assert json_plugin == 'json_reader'


def test_registry_add_entry():
    """Test adding entries to registry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / 'registry.json'
        registry = PluginRegistry(registry_path=registry_path)

        # Add custom entry
        registry.add_entry('.custom', 'custom_reader', priority=10, source='user')

        # Should be able to retrieve it
        plugin = registry.get_plugin_for_extension('.custom')
        assert plugin == 'custom_reader'


def test_registry_priority():
    """Test that higher priority entries win."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / 'registry.json'
        registry = PluginRegistry(registry_path=registry_path)

        # Add two entries for same extension
        registry.add_entry('.test', 'plugin_a', priority=5, source='default')
        registry.add_entry('.test', 'plugin_b', priority=10, source='user')

        # Higher priority should win
        plugin = registry.get_plugin_for_extension('.test')
        assert plugin == 'plugin_b'


def test_registry_url_patterns():
    """Test URL pattern matching."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / 'registry.json'
        registry = PluginRegistry(registry_path=registry_path)

        # Should have default URL patterns
        plugin = registry.get_plugin_for_url('https://example.com/data.json')
        assert plugin == 'http_get'

        plugin = registry.get_plugin_for_url('http://example.com/data.json')
        assert plugin == 'http_get'


def test_registry_url_pattern_specificity():
    """Test that more specific URL patterns win."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / 'registry.json'
        registry = PluginRegistry(registry_path=registry_path)

        # Add generic https pattern
        registry.add_entry('https://', 'http_get', priority=0)

        # Add more specific pattern
        registry.add_entry('https://api.github.com/', 'github_api', priority=0)

        # Specific pattern should win (longer match)
        plugin = registry.get_plugin_for_url('https://api.github.com/repos')
        assert plugin == 'github_api'

        # Generic pattern for other URLs
        plugin = registry.get_plugin_for_url('https://example.com/data')
        assert plugin == 'http_get'


def test_registry_command_mapping():
    """Test shell command mapping."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / 'registry.json'
        registry = PluginRegistry(registry_path=registry_path)

        # Should have command mappings
        plugin = registry.get_plugin_for_command('ls')
        assert plugin == 'ls'


def test_registry_save_and_load():
    """Test saving and loading registry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / 'registry.json'

        # Create and populate registry
        registry1 = PluginRegistry(registry_path=registry_path)
        registry1.add_entry('.custom', 'custom_reader', priority=10, source='user')
        registry1.save()

        # Load in new instance
        registry2 = PluginRegistry(registry_path=registry_path)

        # Should have the custom entry
        plugin = registry2.get_plugin_for_extension('.custom')
        assert plugin == 'custom_reader'

        # Find the entry
        custom_entries = [e for e in registry2.entries if e.pattern == '.custom']
        assert len(custom_entries) > 0
        assert custom_entries[0].source == 'user'


def test_registry_list_patterns():
    """Test listing registry patterns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / 'registry.json'
        registry = PluginRegistry(registry_path=registry_path)

        # Add entries with different sources
        registry.add_entry('.test1', 'plugin1', source='default')
        registry.add_entry('.test2', 'plugin2', source='user')

        # List all
        all_entries = registry.list_patterns()
        assert len(all_entries) > 0

        # List user only
        user_entries = registry.list_patterns(source='user')
        assert any(e.pattern == '.test2' for e in user_entries)
        assert all(e.source == 'user' for e in user_entries)


def test_registry_remove_pattern():
    """Test removing patterns from registry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / 'registry.json'
        registry = PluginRegistry(registry_path=registry_path)

        # Add entry
        registry.add_entry('.test', 'test_plugin', source='user')
        assert registry.get_plugin_for_extension('.test') == 'test_plugin'

        # Remove it
        removed = registry.remove_pattern('.test', source='user')
        assert removed is True

        # Should be gone
        plugin = registry.get_plugin_for_extension('.test')
        assert plugin is None


def test_registry_rebuild_from_plugins():
    """Test rebuilding registry from discovered plugins."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / 'registry.json'
        registry = PluginRegistry(registry_path=registry_path)

        # Add user entry
        registry.add_entry('.custom', 'custom_reader', source='user')

        # Rebuild from plugins
        registry.rebuild_from_plugins()

        # User entry should be preserved
        plugin = registry.get_plugin_for_extension('.custom')
        assert plugin == 'custom_reader'

        # Default entries should still exist
        csv_plugin = registry.get_plugin_for_extension('.csv')
        assert csv_plugin == 'csv_reader'


def test_registry_user_override():
    """Test that user entries override defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / 'registry.json'
        registry = PluginRegistry(registry_path=registry_path)

        # Check default
        plugin = registry.get_plugin_for_extension('.csv')
        assert plugin == 'csv_reader'

        # Add user override with high priority
        registry.add_entry('.csv', 'my_csv_reader', priority=100, source='user')

        # User entry should win
        plugin = registry.get_plugin_for_extension('.csv')
        assert plugin == 'my_csv_reader'


def test_resolve_plugin_url():
    """Test resolve_plugin with URLs."""
    plugin = resolve_plugin('https://example.com/data.json')
    assert plugin == 'http_get'


def test_resolve_plugin_file_extension():
    """Test resolve_plugin with file paths."""
    plugin = resolve_plugin('data.csv')
    assert plugin == 'csv_reader'

    plugin = resolve_plugin('/path/to/file.json')
    assert plugin == 'json_reader'


def test_resolve_plugin_command():
    """Test resolve_plugin with commands."""
    plugin = resolve_plugin('ls')
    assert plugin == 'ls'


def test_resolve_plugin_no_match():
    """Test resolve_plugin with no match."""
    plugin = resolve_plugin('unknown_thing')
    assert plugin is None


def test_registry_entry_dataclass():
    """Test RegistryEntry dataclass."""
    entry = RegistryEntry(
        pattern='.csv',
        plugin_name='csv_reader',
        priority=5,
        source='default'
    )

    assert entry.pattern == '.csv'
    assert entry.plugin_name == 'csv_reader'
    assert entry.priority == 5
    assert entry.source == 'default'


def test_registry_add_replaces_same_source():
    """Test that adding entry replaces existing with same pattern and source."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / 'registry.json'
        registry = PluginRegistry(registry_path=registry_path)

        # Add entry
        registry.add_entry('.test', 'plugin_v1', source='user')

        # Add again with same source - should replace
        registry.add_entry('.test', 'plugin_v2', source='user')

        # Should only have one entry for this pattern/source
        entries = [e for e in registry.entries if e.pattern == '.test' and e.source == 'user']
        assert len(entries) == 1
        assert entries[0].plugin_name == 'plugin_v2'


def test_registry_extension_with_dot():
    """Test that extension lookup works with or without dot."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / 'registry.json'
        registry = PluginRegistry(registry_path=registry_path)

        # Should work both ways
        plugin1 = registry.get_plugin_for_extension('.csv')
        plugin2 = registry.get_plugin_for_extension('csv')

        assert plugin1 == plugin2
        assert plugin1 == 'csv_reader'
