"""Test plugin discovery and fallback mechanisms."""

import textwrap
from pathlib import Path

from jn.discovery import (
    get_cached_plugins,
    get_cached_plugins_with_fallback,
    parse_pep723,
)


def test_pep723_parsing(tmp_path):
    """Test PEP 723 metadata parsing."""
    content = textwrap.dedent("""\
        #!/usr/bin/env python3
        # /// script
        # requires-python = ">=3.11"
        # dependencies = ["pandas>=2.0"]
        # [tool.jn]
        # matches = [".*\\.csv$"]
        # ///

        def reads(config=None):
            pass
        """)
    # Create test file
    test_file = tmp_path / "test.py"
    test_file.write_text(content)

    metadata = parse_pep723(test_file)

    assert metadata["requires-python"] == ">=3.11"
    assert "pandas>=2.0" in metadata["dependencies"]
    assert ".*\\.csv$" in metadata["tool"]["jn"]["matches"]


def test_plugin_discovery_caching(tmp_path):
    """Test that plugins are cached and invalidated properly."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    cache_path = tmp_path / "cache.json"

    # Create a plugin
    plugin_file = plugin_dir / "test.py"
    plugin_file.write_text(textwrap.dedent("""\
        #!/usr/bin/env python3
        # /// script
        # requires-python = ">=3.11"
        # dependencies = []
        # [tool.jn]
        # matches = [".*\\.test$"]
        # ///

        def reads(config=None):
            pass
        """))

    # First discovery - should create cache
    plugins = get_cached_plugins(plugin_dir, cache_path)
    assert "test" in plugins
    assert cache_path.exists()

    # Second discovery - should use cache
    plugins2 = get_cached_plugins(plugin_dir, cache_path)
    assert plugins2 == plugins

    # Modify plugin - should invalidate cache
    plugin_file.write_text(textwrap.dedent("""\
        #!/usr/bin/env python3
        # /// script
        # requires-python = ">=3.11"
        # dependencies = []
        # [tool.jn]
        # matches = [".*\\.test2$"]
        # ///

        def reads(config=None):
            pass
        """))

    # Touch file to update mtime
    import time
    time.sleep(0.01)
    plugin_file.touch()

    # Should re-parse
    plugins3 = get_cached_plugins(plugin_dir, cache_path)
    assert "test" in plugins3
    assert plugins3["test"].matches == [".*\\.test2$"]


def test_plugin_fallback_merges_with_builtins(tmp_path):
    """Test that custom plugins merge with built-ins, not replace them."""
    # Create custom plugin directory with just ONE custom plugin
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    cache_path = tmp_path / "cache.json"

    custom_plugin = plugin_dir / "custom.py"
    custom_plugin.write_text(textwrap.dedent("""\
        #!/usr/bin/env python3
        # /// script
        # requires-python = ">=3.11"
        # dependencies = []
        # [tool.jn]
        # matches = [".*\\.custom$"]
        # ///

        def reads(config=None):
            pass
        """))

    # Load with fallback - should get custom plugin AND all built-ins
    plugins = get_cached_plugins_with_fallback(plugin_dir, cache_path)

    # Should have the custom plugin
    assert "custom" in plugins
    assert any(".*\\.custom$" in m for m in plugins["custom"].matches)

    # Should ALSO have built-in plugins (csv_, json_, yaml_)
    assert "csv_" in plugins
    assert "json_" in plugins
    assert "yaml_" in plugins

    # Verify we got more than just the one custom plugin
    assert len(plugins) > 1


def test_plugin_fallback_custom_overrides_builtin(tmp_path):
    """Test that custom plugins override built-ins with same name."""
    # Create custom plugin directory with a plugin that overrides csv_
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    cache_path = tmp_path / "cache.json"

    custom_csv = plugin_dir / "csv_.py"
    custom_csv.write_text(textwrap.dedent("""\
        #!/usr/bin/env python3
        # /// script
        # requires-python = ">=3.11"
        # dependencies = []
        # [tool.jn]
        # matches = [".*\\.customcsv$"]
        # ///

        def reads(config=None):
            pass
        """))

    # Load with fallback
    plugins = get_cached_plugins_with_fallback(plugin_dir, cache_path)

    # Should have csv_ plugin
    assert "csv_" in plugins

    # But it should be the CUSTOM one (matches .customcsv, not .csv)
    assert any(".*\\.customcsv$" in m for m in plugins["csv_"].matches)
    assert not any(".*\\.csv$" in m for m in plugins["csv_"].matches)

    # Should still have other built-ins
    assert "json_" in plugins
    assert "yaml_" in plugins


def test_plugin_fallback_disabled(tmp_path):
    """Test that fallback can be disabled."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    cache_path = tmp_path / "cache.json"

    # Don't create any custom plugins

    # Load with fallback DISABLED
    plugins = get_cached_plugins_with_fallback(
        plugin_dir, cache_path, fallback_to_builtin=False
    )

    # Should have NO plugins (empty custom dir, fallback disabled)
    assert len(plugins) == 0


def test_plugin_fallback_empty_custom_dir(tmp_path):
    """Test that empty custom dir falls back to built-ins."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    cache_path = tmp_path / "cache.json"

    # Don't create any custom plugins

    # Load with fallback enabled (default)
    plugins = get_cached_plugins_with_fallback(plugin_dir, cache_path)

    # Should have built-in plugins
    assert "csv_" in plugins
    assert "json_" in plugins
    assert "yaml_" in plugins
    assert len(plugins) > 0
