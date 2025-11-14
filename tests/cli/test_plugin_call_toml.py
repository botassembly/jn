import json


def test_plugin_call_toml_read(invoke):
    """Test reading TOML to NDJSON."""
    toml_content = """
[project]
name = "jn"
version = "1.0.0"

[project.dependencies]
click = ">=8.0"
ruamel-yaml = ">=0.18.0"
"""
    res = invoke(
        ["plugin", "call", "toml_", "--mode", "read"], input_data=toml_content
    )
    assert res.exit_code == 0
    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["project"]["name"] == "jn"
    assert data["project"]["version"] == "1.0.0"
    assert "click" in data["project"]["dependencies"]


def test_plugin_call_toml_write(invoke):
    """Test writing NDJSON to TOML."""
    ndjson = '{"project": {"name": "jn", "version": "1.0.0"}}\n'
    res = invoke(
        ["plugin", "call", "toml_", "--mode", "write"], input_data=ndjson
    )
    assert res.exit_code == 0
    output = res.output.strip()
    assert "[project]" in output
    assert 'name = "jn"' in output
    assert 'version = "1.0.0"' in output


def test_plugin_call_toml_merge(invoke):
    """Test merging multiple NDJSON records into TOML."""
    ndjson = '{"project": {"name": "jn"}}\n{"project": {"version": "1.0.0"}}\n'
    res = invoke(
        ["plugin", "call", "toml_", "--mode", "write"], input_data=ndjson
    )
    assert res.exit_code == 0
    output = res.output.strip()
    assert "[project]" in output
    assert 'name = "jn"' in output
    assert 'version = "1.0.0"' in output
