import json
from pathlib import Path


def test_plugin_list_text(invoke):
    res = invoke(["plugin", "list"])
    assert res.exit_code == 0
    # Built-ins should be present (csv is now Zig binary, json_/yaml_ are Python)
    assert "csv" in res.output
    assert "json" in res.output or "json_" in res.output
    assert "yaml_" in res.output


def test_plugin_list_json_and_custom_merge(invoke, tmp_path):
    # Create a custom plugin that should be merged with built-ins
    home = tmp_path / "jn_home"
    (home / "plugins").mkdir(parents=True)
    custom = home / "plugins" / "custom.py"
    custom.write_text(
        """#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = ['.*\\.custom$']
# ///

def reads(config=None):
    pass
"""
    )

    res = invoke(["--home", str(home), "plugin", "list", "--format", "json"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert "custom" in data
    # Built-ins still present (csv is now Zig binary, json can be json or json_)
    assert "csv" in data
    assert "json" in data or "json_" in data
    assert "yaml_" in data


def test_plugin_default_to_list(invoke):
    """Test that 'jn plugin' without subcommand defaults to 'list'."""
    result = invoke(["plugin"])
    assert result.exit_code == 0
    # Should show list of plugins (csv is now Zig binary)
    assert "csv" in result.output
    assert "json" in result.output or "json_" in result.output


def test_plugin_list_with_plugin_without_description(invoke, tmp_path):
    """Test plugin list displays fallback for plugins without description."""
    home = tmp_path / "jn_home"
    (home / "plugins").mkdir(parents=True)
    custom = home / "plugins" / "nodesc.py"
    # Plugin without description or docstring
    custom.write_text(
        """#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = ['.*\\.nd1$', '.*\\.nd2$', '.*\\.nd3$']
# ///

def reads(config=None):
    pass
"""
    )

    res = invoke(["--home", str(home), "plugin", "list"])
    assert res.exit_code == 0
    # Should show fallback description with patterns
    assert "nodesc" in res.output
    assert "Matches:" in res.output
