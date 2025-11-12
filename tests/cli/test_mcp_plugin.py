"""Tests for MCP protocol plugin."""
import json
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def mcp_plugin():
    """Path to MCP plugin."""
    return Path(__file__).parent.parent.parent / "jn_home" / "plugins" / "protocols" / "mcp_.py"


def test_mcp_plugin_syntax(mcp_plugin):
    """Test that MCP plugin has valid Python syntax."""
    result = subprocess.run(
        ["python", "-m", "py_compile", str(mcp_plugin)],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Syntax error: {result.stderr}"


def test_mcp_plugin_help(mcp_plugin):
    """Test MCP plugin CLI help."""
    result = subprocess.run(
        ["uv", "run", "--script", str(mcp_plugin), "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "--mode" in result.stdout
    assert "read" in result.stdout
    assert "write" in result.stdout


def test_mcp_plugin_requires_mode(mcp_plugin):
    """Test that plugin requires --mode argument."""
    result = subprocess.run(
        ["uv", "run", "--script", str(mcp_plugin), "@biomcp"],
        capture_output=True,
        text=True
    )
    assert result.returncode != 0


def test_mcp_plugin_profile_not_found(mcp_plugin):
    """Test error when profile doesn't exist."""
    result = subprocess.run(
        ["uv", "run", "--script", str(mcp_plugin), "--mode", "read", "@nonexistent"],
        capture_output=True,
        text=True,
        timeout=10
    )

    assert result.returncode == 0  # Errors are returned as NDJSON
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) >= 1

    record = json.loads(lines[0])
    assert record.get("_error") is True
    assert "profile_error" in record.get("type", "")


def test_mcp_plugin_matches_profile_pattern(mcp_plugin):
    """Test that plugin metadata matches @ pattern."""
    content = mcp_plugin.read_text()

    # Check PEP 723 metadata
    assert "# [tool.jn]" in content
    assert "matches" in content
    assert "^@[a-zA-Z0-9_-]+" in content

    # Should NOT match legacy patterns
    assert "^mcp://" not in content


def test_mcp_plugin_has_clean_interface(mcp_plugin):
    """Test that plugin has clean reads/writes interface."""
    content = mcp_plugin.read_text()

    # Should have reads and writes
    assert "def reads(url: str, **params)" in content
    assert "def writes(url: str | None = None, **config)" in content

    # Should NOT have legacy functions
    assert "parse_mcp_url" not in content
    assert "load_server_config" not in content
    assert "HAS_PROFILE_SYSTEM" not in content


# Integration tests using test fixture profiles
# These test the full pipeline: CLI → plugin → profile system
# Note: MCP profiles are in tests/fixtures (not bundled), set via conftest.py

def test_mcp_profile_biomcp_exists():
    """Test that BioMCP profile exists in test fixtures."""
    biomcp_meta = Path(__file__).parent.parent / "fixtures" / "profiles" / "mcp" / "biomcp" / "_meta.json"
    assert biomcp_meta.exists(), f"BioMCP profile not found at {biomcp_meta}"

    meta = json.loads(biomcp_meta.read_text())
    assert meta["command"] == "uv"
    assert "biomcp" in " ".join(meta["args"])


def test_mcp_profile_context7_exists():
    """Test that Context7 profile exists in test fixtures."""
    context7_meta = Path(__file__).parent.parent / "fixtures" / "profiles" / "mcp" / "context7" / "_meta.json"
    assert context7_meta.exists(), f"Context7 profile not found at {context7_meta}"

    meta = json.loads(context7_meta.read_text())
    assert meta["command"] == "npx"
    assert "context7" in " ".join(meta["args"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
