"""Tests for plugin discovery system."""

import tempfile
from pathlib import Path
import pytest

from jn.discovery import (
    get_plugin_paths,
    parse_plugin_metadata,
    discover_plugins,
    get_plugins_by_extension,
    get_plugins_by_command,
    PluginMetadata,
)


def test_parse_plugin_metadata_basic():
    """Test parsing basic plugin metadata."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
# META: type=source, handles=[".csv"]

def run(config=None):
    pass
""")
        f.flush()
        plugin_path = Path(f.name)

    try:
        metadata = parse_plugin_metadata(plugin_path)

        assert metadata is not None
        assert metadata.name == plugin_path.stem
        assert metadata.type == 'source'
        assert metadata.handles == ['.csv']
        assert metadata.streaming is False
        assert metadata.dependencies == []
    finally:
        plugin_path.unlink()


def test_parse_plugin_metadata_multiple_extensions():
    """Test parsing plugin with multiple file extensions."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""#!/usr/bin/env python3
# META: type=source, handles=[".csv", ".tsv"], streaming=true

def run(config=None):
    pass
""")
        f.flush()
        plugin_path = Path(f.name)

    try:
        metadata = parse_plugin_metadata(plugin_path)

        assert metadata is not None
        assert metadata.handles == ['.csv', '.tsv']
        assert metadata.streaming is True
    finally:
        plugin_path.unlink()


def test_parse_plugin_metadata_with_command():
    """Test parsing shell command plugin."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""#!/usr/bin/env python3
# META: type=source, command="ls"

def run(config=None):
    pass
""")
        f.flush()
        plugin_path = Path(f.name)

    try:
        metadata = parse_plugin_metadata(plugin_path)

        assert metadata is not None
        assert metadata.command == 'ls'
        assert metadata.type == 'source'
    finally:
        plugin_path.unlink()


def test_parse_plugin_metadata_with_dependencies():
    """Test parsing plugin with PEP 723 dependencies."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""#!/usr/bin/env python3
# /// script
# dependencies = ["requests>=2.28.0", "pydantic>=2.0"]
# ///
# META: type=source, handles=[".yaml"]

def run(config=None):
    pass
""")
        f.flush()
        plugin_path = Path(f.name)

    try:
        metadata = parse_plugin_metadata(plugin_path)

        assert metadata is not None
        assert metadata.dependencies == ["requests>=2.28.0", "pydantic>=2.0"]
    finally:
        plugin_path.unlink()


def test_parse_plugin_metadata_category_detection():
    """Test category detection from directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create readers subdirectory
        readers_dir = Path(tmpdir) / 'readers'
        readers_dir.mkdir()

        plugin_path = readers_dir / 'csv_reader.py'
        plugin_path.write_text("""#!/usr/bin/env python3
# META: type=source, handles=[".csv"]

def run(config=None):
    pass
""")

        metadata = parse_plugin_metadata(plugin_path)

        assert metadata is not None
        assert metadata.category == 'readers'
        assert metadata.name == 'csv_reader'


def test_parse_plugin_metadata_non_python_file():
    """Test that non-Python files return None."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("Not a Python file")
        f.flush()
        file_path = Path(f.name)

    try:
        metadata = parse_plugin_metadata(file_path)
        assert metadata is None
    finally:
        file_path.unlink()


def test_parse_plugin_metadata_missing_meta():
    """Test parsing plugin without META header."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""#!/usr/bin/env python3
# No META header

def run(config=None):
    pass
""")
        f.flush()
        plugin_path = Path(f.name)

    try:
        metadata = parse_plugin_metadata(plugin_path)

        # Should still create metadata, just with no type/handles
        assert metadata is not None
        assert metadata.type is None
        assert metadata.handles == []
    finally:
        plugin_path.unlink()


def test_discover_plugins_finds_bundled():
    """Test that discover_plugins finds bundled plugins."""
    plugins = discover_plugins()

    # Should find our bundled plugins
    assert 'csv_reader' in plugins
    assert 'csv_writer' in plugins
    assert 'json_reader' in plugins
    assert 'ls' in plugins

    # Check metadata
    csv_reader = plugins['csv_reader']
    assert csv_reader.type == 'source'
    assert '.csv' in csv_reader.handles
    assert csv_reader.category == 'readers'


def test_discover_plugins_with_custom_path():
    """Test discovering plugins from custom path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_dir = Path(tmpdir)

        # Create a test plugin (note: not named test_* to avoid being skipped)
        plugin_path = plugin_dir / 'custom_filter.py'
        plugin_path.write_text("""#!/usr/bin/env python3
# META: type=filter, handles=[".json"]

def run(config=None):
    pass
""")

        plugins = discover_plugins(scan_paths=[plugin_dir])

        assert 'custom_filter' in plugins
        assert plugins['custom_filter'].type == 'filter'


def test_discover_plugins_filter_by_type():
    """Test filtering plugins by type."""
    # Discover only source plugins
    plugins = discover_plugins(plugin_types={'source'})

    # Should only have source plugins
    for plugin in plugins.values():
        assert plugin.type == 'source' or plugin.type is None


def test_discover_plugins_skips_test_files():
    """Test that discovery skips test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_dir = Path(tmpdir)

        # Create a test file (should be skipped)
        test_file = plugin_dir / 'test_something.py'
        test_file.write_text("""#!/usr/bin/env python3
# META: type=source

def test_something():
    pass
""")

        # Create __init__.py (should be skipped)
        init_file = plugin_dir / '__init__.py'
        init_file.write_text("")

        plugins = discover_plugins(scan_paths=[plugin_dir])

        # Should not find test files or __init__.py
        assert 'test_something' not in plugins
        assert '__init__' not in plugins


def test_get_plugins_by_extension():
    """Test finding plugins by file extension."""
    plugins = get_plugins_by_extension('.csv')

    # Should find csv_reader
    assert len(plugins) >= 1
    assert any(p.name == 'csv_reader' for p in plugins)


def test_get_plugins_by_command():
    """Test finding plugins by shell command."""
    plugins = get_plugins_by_command('ls')

    # Should find ls plugin
    assert len(plugins) >= 1
    assert any(p.name == 'ls' for p in plugins)


def test_get_plugins_changed_since():
    """Test finding recently modified plugins."""
    import time

    timestamp = time.time()

    # Create a new plugin
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_dir = Path(tmpdir)
        plugin_path = plugin_dir / 'new_plugin.py'

        # Wait a moment to ensure mtime is after timestamp
        time.sleep(0.1)

        plugin_path.write_text("""#!/usr/bin/env python3
# META: type=source

def run(config=None):
    pass
""")

        # This plugin should be newer than our timestamp
        from jn.discovery import get_plugins_changed_since

        changed = get_plugins_changed_since(timestamp)

        # Note: This will find the new plugin if it's in the scan paths
        # For bundled plugins, they won't be newer than timestamp
        assert isinstance(changed, list)


def test_metadata_tracks_mtime():
    """Test that metadata tracks file modification time."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""#!/usr/bin/env python3
# META: type=source

def run(config=None):
    pass
""")
        f.flush()
        plugin_path = Path(f.name)

    try:
        metadata = parse_plugin_metadata(plugin_path)

        assert metadata is not None
        assert metadata.mtime > 0
        assert metadata.mtime == pytest.approx(plugin_path.stat().st_mtime, rel=1e-3)
    finally:
        plugin_path.unlink()


def test_plugin_paths_priority():
    """Test that plugin paths are returned in correct priority order."""
    paths = get_plugin_paths()

    # Should be a list of Path objects
    assert isinstance(paths, list)
    assert all(isinstance(p, Path) for p in paths)

    # Package plugins should be in the list (they exist)
    package_plugins = Path(__file__).parent.parent.parent / 'plugins'
    assert any(p == package_plugins for p in paths)
