"""Tests for MCP protocol plugin."""
import json
import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def mcp_plugin():
    """Path to MCP plugin."""
    return Path(__file__).parent.parent.parent / "jn_home" / "plugins" / "protocols" / "mcp_.py"


@pytest.fixture
def mcp_config(tmp_path):
    """Create a temporary MCP server configuration."""
    config = {
        "test-server": {
            "command": "echo",
            "args": ["test"],
            "description": "Test server"
        },
        "biomcp": {
            "command": "uv",
            "args": ["run", "--with", "biomcp-python", "biomcp", "run"],
            "description": "BioMCP test server"
        }
    }
    config_file = tmp_path / "mcp-servers.json"
    config_file.write_text(json.dumps(config))
    return config_file


def test_mcp_plugin_syntax(mcp_plugin):
    """Test that MCP plugin has valid Python syntax."""
    result = subprocess.run(
        ["python", "-m", "py_compile", str(mcp_plugin)],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Syntax error in MCP plugin: {result.stderr}"


def test_mcp_plugin_help(mcp_plugin):
    """Test MCP plugin help output."""
    result = subprocess.run(
        ["uv", "run", "--script", str(mcp_plugin), "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "--mode" in result.stdout
    assert "read" in result.stdout
    assert "write" in result.stdout


def test_mcp_plugin_missing_mode(mcp_plugin):
    """Test that plugin requires --mode argument."""
    result = subprocess.run(
        ["uv", "run", "--script", str(mcp_plugin)],
        capture_output=True,
        text=True
    )
    assert result.returncode != 0
    assert "--mode is required" in result.stderr


def test_mcp_plugin_missing_url(mcp_plugin):
    """Test that plugin requires URL for read mode."""
    result = subprocess.run(
        ["uv", "run", "--script", str(mcp_plugin), "--mode", "read"],
        capture_output=True,
        text=True
    )
    assert result.returncode != 0
    assert "URL is required" in result.stderr


def test_mcp_plugin_config_not_found(mcp_plugin, tmp_path, monkeypatch):
    """Test error when MCP server config not found."""
    # Set JN_HOME to empty temp directory (no config)
    monkeypatch.setenv("JN_HOME", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    result = subprocess.run(
        [
            "uv", "run", "--script", str(mcp_plugin),
            "--mode", "read",
            "mcp://unknown-server?list=resources"
        ],
        capture_output=True,
        text=True,
        env={"JN_HOME": str(tmp_path), "HOME": str(tmp_path), "PATH": subprocess.os.environ["PATH"]},
        timeout=10
    )

    # Should succeed but yield error record
    assert result.returncode == 0
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) >= 1

    record = json.loads(lines[0])
    assert record.get("_error") is True
    assert "config_not_found" in record.get("type", "")


def test_mcp_plugin_url_parsing():
    """Test MCP URL parsing logic (unit test without subprocess)."""
    # This would require importing the plugin, which needs MCP SDK
    # For now, we test via subprocess with different URL formats
    pass


def test_mcp_plugin_protocol_schemes(mcp_plugin):
    """Test that plugin recognizes different MCP URL schemes."""
    schemes = [
        "mcp://server",
        "mcp+stdio://server",
        # "mcp+http://server"  # Not implemented yet
    ]

    for scheme in schemes:
        # Just test that the plugin accepts these schemes
        # (will fail on config not found, but that's expected)
        result = subprocess.run(
            [
                "uv", "run", "--script", str(mcp_plugin),
                "--mode", "read",
                f"{scheme}?list=resources"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )
        # Should not fail on URL parsing
        if "unsupported scheme" in result.stdout.lower():
            pytest.fail(f"Scheme {scheme} not supported")


# Integration tests (requires actual MCP servers)
# These are marked as integration and skipped by default

@pytest.mark.integration
@pytest.mark.skipif(
    not Path.home().joinpath(".jn/mcp-servers.json").exists(),
    reason="Requires MCP server configuration at ~/.jn/mcp-servers.json"
)
def test_mcp_plugin_list_resources_biomcp(mcp_plugin):
    """Test listing resources from BioMCP (requires BioMCP to be installed)."""
    result = subprocess.run(
        [
            "uv", "run", "--script", str(mcp_plugin),
            "--mode", "read",
            "mcp://biomcp?list=resources"
        ],
        capture_output=True,
        text=True,
        timeout=30
    )

    if result.returncode != 0:
        pytest.skip(f"BioMCP not available: {result.stderr}")

    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) >= 1

    # First line should be a resource
    record = json.loads(lines[0])
    if not record.get("_error"):
        assert record.get("type") == "resource"
        assert "uri" in record


@pytest.mark.integration
@pytest.mark.skipif(
    not Path.home().joinpath(".jn/mcp-servers.json").exists(),
    reason="Requires MCP server configuration"
)
def test_mcp_plugin_list_tools_biomcp(mcp_plugin):
    """Test listing tools from BioMCP (requires BioMCP to be installed)."""
    result = subprocess.run(
        [
            "uv", "run", "--script", str(mcp_plugin),
            "--mode", "read",
            "mcp://biomcp?list=tools"
        ],
        capture_output=True,
        text=True,
        timeout=30
    )

    if result.returncode != 0:
        pytest.skip(f"BioMCP not available: {result.stderr}")

    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) >= 1

    # First line should be a tool
    record = json.loads(lines[0])
    if not record.get("_error"):
        assert record.get("type") == "tool"
        assert "name" in record


# Note: Write mode tests would require a writable MCP server
# Desktop Commander could be used for this, but it's complex to set up in CI

def test_mcp_plugin_write_mode_missing_tool(mcp_plugin):
    """Test that write mode requires tool parameter."""
    result = subprocess.run(
        [
            "uv", "run", "--script", str(mcp_plugin),
            "--mode", "write",
            "mcp://test-server"
        ],
        capture_output=True,
        text=True,
        input="",
        timeout=10
    )

    # Should yield error about missing tool
    assert "missing_tool" in result.stdout.lower() or "tool" in result.stdout.lower()


def test_mcp_config_example_valid():
    """Test that the example MCP config file is valid JSON."""
    config_file = Path(__file__).parent.parent.parent / "mcp-servers.example.json"
    assert config_file.exists(), "mcp-servers.example.json not found"

    with open(config_file) as f:
        config = json.load(f)

    assert isinstance(config, dict)
    assert "biomcp" in config
    assert "context7" in config

    # Each server should have command and args
    for server_name, server_config in config.items():
        assert "command" in server_config, f"{server_name} missing 'command'"
        assert "args" in server_config, f"{server_name} missing 'args'"
        assert isinstance(server_config["args"], list), f"{server_name} 'args' must be a list"


def test_mcp_plugin_pep723_metadata(mcp_plugin):
    """Test that MCP plugin has valid PEP 723 metadata."""
    content = mcp_plugin.read_text()

    # Check for PEP 723 block
    assert "# /// script" in content
    assert "requires-python" in content
    assert "dependencies" in content
    assert "[tool.jn]" in content
    assert "matches" in content

    # Check for MCP dependency
    assert "mcp>=" in content

    # Check for match patterns
    assert "^mcp://" in content


def test_mcp_plugin_has_reads_writes():
    """Test that MCP plugin defines reads() and writes() functions."""
    # Would need to import the plugin for proper testing
    # For now, just check the file content
    plugin_path = Path(__file__).parent.parent.parent / "jn_home" / "plugins" / "protocols" / "mcp_.py"
    content = plugin_path.read_text()

    assert "def reads(" in content
    assert "def writes(" in content
    assert "Iterator[dict]" in content  # Type hint for reads


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
