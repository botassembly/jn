def test_plugin_info(invoke):
    res = invoke(["plugin", "info", "csv_"])
    assert res.exit_code == 0
    # Basic fields
    assert "Plugin: csv_" in res.output
    assert "Type:" in res.output
    assert "Methods:" in res.output
    assert "Matches:" in res.output


def test_plugin_info_not_found(invoke):
    """Test plugin info with non-existent plugin."""
    result = invoke(["plugin", "info", "nonexistent_plugin"])
    assert result.exit_code == 1
    assert "Error: Plugin 'nonexistent_plugin' not found" in result.output
    assert "Available plugins:" in result.output


def test_plugin_info_with_dependencies_and_python_version(invoke, tmp_path):
    """Test plugin info displays dependencies and python version."""
    home = tmp_path / "jn_home"
    (home / "plugins").mkdir(parents=True)
    plugin_with_deps = home / "plugins" / "withdeps.py"
    plugin_with_deps.write_text(
        '''#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.0", "numpy>=1.20"]
# [tool.jn]
# matches = ['.*\\.wd$']
# ///
"""Plugin with dependencies."""

def reads(config=None):
    """Read data from source."""
    pass
'''
    )

    res = invoke(["--home", str(home), "plugin", "info", "withdeps"])
    assert res.exit_code == 0
    assert "Dependencies:" in res.output
    assert "pandas>=2.0" in res.output
    assert "numpy>=1.20" in res.output
    assert "Requires Python: >=3.12" in res.output
    assert "Read data from source" in res.output  # method doc


def test_plugin_info_filter_plugin(invoke, tmp_path):
    """Test plugin info displays usage for filter-type plugin."""
    home = tmp_path / "jn_home"
    (home / "plugins").mkdir(parents=True)
    filter_plugin = home / "plugins" / "myfilter.py"
    filter_plugin.write_text(
        '''#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = []
# ///
"""A custom filter."""

def filters(config=None):
    """Apply custom filter."""
    pass
'''
    )

    res = invoke(["--home", str(home), "plugin", "info", "myfilter"])
    assert res.exit_code == 0
    assert "jn plugin call myfilter" in res.output  # filter usage example


def test_plugin_info_write_only_plugin(invoke, tmp_path):
    """Test plugin info displays usage for write-only plugin."""
    home = tmp_path / "jn_home"
    (home / "plugins").mkdir(parents=True)
    write_plugin = home / "plugins" / "writeonly.py"
    write_plugin.write_text(
        '''#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = ['.*\\.wo$']
# ///

def writes(config=None):
    pass
'''
    )

    res = invoke(["--home", str(home), "plugin", "info", "writeonly"])
    assert res.exit_code == 0
    assert "jn put output" in res.output or "Write using" in res.output


def test_plugin_info_read_only_plugin(invoke, tmp_path):
    """Test plugin info displays usage for read-only plugin."""
    home = tmp_path / "jn_home"
    (home / "plugins").mkdir(parents=True)
    read_plugin = home / "plugins" / "readonly.py"
    read_plugin.write_text(
        '''#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = ['.*\\.ro$']
# ///

def reads(config=none):
    pass
'''
    )

    res = invoke(["--home", str(home), "plugin", "info", "readonly"])
    assert res.exit_code == 0
    assert "jn cat source" in res.output or "Read using" in res.output

