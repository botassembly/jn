"""Tests for MCP profile system."""
import json
from pathlib import Path

import pytest

from jn.profiles.mcp import (
    ProfileError,
    find_profile_paths,
    load_hierarchical_profile,
    list_server_tools,
    resolve_profile_reference,
    substitute_env_vars,
    substitute_env_vars_recursive,
)


def test_find_profile_paths():
    """Test profile path discovery."""
    paths = find_profile_paths()
    assert len(paths) >= 1  # At least bundled profiles
    assert all(isinstance(p, Path) for p in paths)


def test_substitute_env_vars(monkeypatch):
    """Test environment variable substitution."""
    monkeypatch.setenv("TEST_VAR", "test-value")

    result = substitute_env_vars("Bearer ${TEST_VAR}")
    assert result == "Bearer test-value"


def test_substitute_env_vars_missing(monkeypatch):
    """Test error when env var is missing."""
    monkeypatch.delenv("MISSING_VAR", raising=False)

    with pytest.raises(ProfileError, match="Environment variable MISSING_VAR not set"):
        substitute_env_vars("Value: ${MISSING_VAR}")


def test_substitute_env_vars_recursive(monkeypatch):
    """Test recursive env var substitution in nested structures."""
    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("BASE_URL", "https://example.com")

    data = {
        "url": "${BASE_URL}/api",
        "headers": {
            "Authorization": "Bearer ${API_KEY}"
        },
        "timeout": 30,
        "list": ["${BASE_URL}", "static"]
    }

    result = substitute_env_vars_recursive(data)

    assert result["url"] == "https://example.com/api"
    assert result["headers"]["Authorization"] == "Bearer secret-key"
    assert result["timeout"] == 30
    assert result["list"] == ["https://example.com", "static"]


def test_load_hierarchical_profile_biomcp():
    """Test loading BioMCP profile."""
    profile = load_hierarchical_profile("biomcp")

    assert profile["command"] == "uv"
    assert "biomcp" in " ".join(profile["args"])
    assert profile["description"]
    assert profile["transport"] == "stdio"


def test_load_hierarchical_profile_with_tool():
    """Test loading profile with tool definition."""
    profile = load_hierarchical_profile("biomcp", "search")

    # Should have both _meta and tool info
    assert profile["command"] == "uv"
    assert profile["tool"] == "search"
    assert "parameters" in profile


def test_load_hierarchical_profile_not_found():
    """Test loading non-existent profile."""
    with pytest.raises(ProfileError, match="MCP server profile not found"):
        load_hierarchical_profile("nonexistent-server-xyz")


def test_list_server_tools():
    """Test listing tools for a server."""
    tools = list_server_tools("biomcp")

    assert len(tools) >= 1
    assert "search" in tools
    assert "trial_search" in tools or "variant_search" in tools
    # _meta.json should not be in the list
    assert "_meta" not in tools


def test_resolve_profile_reference_simple():
    """Test resolving simple profile reference."""
    server_config, operation = resolve_profile_reference("@biomcp")

    assert server_config["command"] == "uv"
    assert operation["type"] == "list_resources"
    assert operation["params"] == {}


def test_resolve_profile_reference_with_tool_path():
    """Test resolving profile reference with tool in path."""
    server_config, operation = resolve_profile_reference("@biomcp/search")

    assert server_config["command"] == "uv"
    assert operation["type"] == "call_tool"
    assert operation["tool"] == "search"


def test_resolve_profile_reference_with_query():
    """Test resolving profile reference with query params."""
    server_config, operation = resolve_profile_reference("@biomcp?list=tools")

    assert server_config["command"] == "uv"
    assert operation["type"] == "list_tools"


def test_resolve_profile_reference_with_tool_and_params():
    """Test resolving profile reference with tool and params."""
    server_config, operation = resolve_profile_reference(
        "@biomcp/search?gene=BRAF&disease=Melanoma"
    )

    assert server_config["command"] == "uv"
    assert operation["type"] == "call_tool"
    assert operation["tool"] == "search"
    assert operation["params"]["gene"] == "BRAF"
    assert operation["params"]["disease"] == "Melanoma"


def test_resolve_profile_reference_with_resource():
    """Test resolving profile reference for reading a resource."""
    server_config, operation = resolve_profile_reference(
        "@biomcp?resource=resource://trials/NCT12345"
    )

    assert server_config["command"] == "uv"
    assert operation["type"] == "read_resource"
    assert operation["resource"] == "resource://trials/NCT12345"


def test_resolve_profile_reference_invalid():
    """Test invalid profile reference (missing @)."""
    with pytest.raises(ProfileError, match="Invalid profile reference"):
        resolve_profile_reference("biomcp/search")


def test_resolve_profile_reference_with_params_dict():
    """Test resolving with params as dict argument."""
    server_config, operation = resolve_profile_reference(
        "@biomcp/search",
        params={"gene": "TP53", "disease": "Lung Cancer"}
    )

    assert operation["type"] == "call_tool"
    assert operation["tool"] == "search"
    assert operation["params"]["gene"] == "TP53"
    assert operation["params"]["disease"] == "Lung Cancer"


def test_context7_profile():
    """Test Context7 profile loading."""
    profile = load_hierarchical_profile("context7")

    assert profile["command"] == "npx"
    assert "context7" in " ".join(profile["args"])


def test_desktop_commander_profile():
    """Test Desktop Commander profile loading."""
    profile = load_hierarchical_profile("desktop-commander")

    assert profile["command"] == "npx"
    assert "desktop-commander" in " ".join(profile["args"])


def test_profile_json_validity():
    """Test that all bundled profile JSON files are valid."""
    profile_dir = Path(__file__).parent.parent.parent / "jn_home" / "profiles" / "mcp"

    if not profile_dir.exists():
        pytest.skip("MCP profile directory not found")

    for json_file in profile_dir.rglob("*.json"):
        # Should be able to parse all JSON files
        with open(json_file) as f:
            data = json.load(f)
            assert isinstance(data, dict), f"Invalid profile: {json_file}"


def test_profile_meta_structure():
    """Test that _meta.json files have required fields."""
    profile_dir = Path(__file__).parent.parent.parent / "jn_home" / "profiles" / "mcp"

    if not profile_dir.exists():
        pytest.skip("MCP profile directory not found")

    for meta_file in profile_dir.rglob("_meta.json"):
        with open(meta_file) as f:
            meta = json.load(f)

            assert "command" in meta, f"{meta_file} missing 'command'"
            assert "args" in meta, f"{meta_file} missing 'args'"
            assert isinstance(meta["args"], list), f"{meta_file} 'args' must be a list"
            assert "description" in meta, f"{meta_file} missing 'description'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
