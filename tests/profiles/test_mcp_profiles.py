"""Tests for MCP profile system."""
import pytest

from jn.profiles.mcp import (
    ProfileError,
    load_hierarchical_profile,
    list_server_tools,
    resolve_profile_reference,
    substitute_env_vars,
    substitute_env_vars_recursive,
)


# Environment variable substitution tests

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
    """Test recursive substitution in nested structures."""
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("URL", "https://api.example.com")

    data = {
        "url": "${URL}/v1",
        "headers": {"Authorization": "Bearer ${API_KEY}"},
        "list": ["${URL}", "static"]
    }

    result = substitute_env_vars_recursive(data)

    assert result["url"] == "https://api.example.com/v1"
    assert result["headers"]["Authorization"] == "Bearer secret"
    assert result["list"] == ["https://api.example.com", "static"]


# Profile loading tests

def test_load_hierarchical_profile():
    """Test loading profile with _meta.json."""
    profile = load_hierarchical_profile("biomcp")

    assert profile["command"] == "uv"
    assert "biomcp" in " ".join(profile["args"])


def test_load_hierarchical_profile_with_tool():
    """Test loading profile merges _meta + tool definition."""
    profile = load_hierarchical_profile("biomcp", "search")

    # Should have both _meta and tool info merged
    assert profile["command"] == "uv"  # from _meta
    assert profile["tool"] == "search"  # from search.json
    assert "parameters" in profile  # from search.json


def test_load_hierarchical_profile_not_found():
    """Test error for non-existent profile."""
    with pytest.raises(ProfileError, match="MCP server profile not found"):
        load_hierarchical_profile("nonexistent-xyz")


def test_list_server_tools():
    """Test listing tools from profile directory."""
    tools = list_server_tools("biomcp")

    assert "search" in tools
    assert "_meta" not in tools  # Should exclude _meta.json


# Profile reference resolution tests

def test_resolve_simple_reference():
    """Test @server resolves to list_resources operation."""
    server_config, operation = resolve_profile_reference("@biomcp")

    assert server_config["command"] == "uv"
    assert operation["type"] == "list_resources"
    assert operation["params"] == {}


def test_resolve_with_tool_in_path():
    """Test @server/tool resolves to call_tool operation."""
    server_config, operation = resolve_profile_reference("@biomcp/search")

    assert operation["type"] == "call_tool"
    assert operation["tool"] == "search"


def test_resolve_with_query_params():
    """Test @server/tool?param=value merges params."""
    server_config, operation = resolve_profile_reference(
        "@biomcp/search?gene=BRAF&disease=Melanoma"
    )

    assert operation["type"] == "call_tool"
    assert operation["tool"] == "search"
    assert operation["params"]["gene"] == "BRAF"
    assert operation["params"]["disease"] == "Melanoma"


def test_resolve_with_list_operation():
    """Test @server?list=tools resolves to list_tools."""
    server_config, operation = resolve_profile_reference("@biomcp?list=tools")

    assert operation["type"] == "list_tools"


def test_resolve_with_resource():
    """Test @server?resource=uri resolves to read_resource."""
    server_config, operation = resolve_profile_reference(
        "@biomcp?resource=resource://trials/NCT12345"
    )

    assert operation["type"] == "read_resource"
    assert operation["resource"] == "resource://trials/NCT12345"


def test_resolve_with_params_dict():
    """Test params dict merges with URL query params."""
    server_config, operation = resolve_profile_reference(
        "@biomcp/search",
        params={"gene": "TP53"}
    )

    assert operation["params"]["gene"] == "TP53"


def test_resolve_invalid_reference():
    """Test error when reference doesn't start with @."""
    with pytest.raises(ProfileError, match="Invalid profile reference"):
        resolve_profile_reference("biomcp/search")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
