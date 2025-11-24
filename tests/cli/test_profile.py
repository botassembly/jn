"""Tests for profile CLI commands.

Tests use profiles from tests/jn_home/profiles/:
- HTTP: @testapi/users, @testapi/projects
- MCP: @biomcp/search, @desktop-commander/execute, etc.
"""

import json


def test_profile_list_text(invoke):
    """Test profile list shows all profiles."""
    res = invoke(["profile", "list"])
    assert res.exit_code == 0
    # HTTP test profiles should be present
    assert "@testapi/users" in res.output
    assert "@testapi/projects" in res.output
    # MCP test profiles should be present
    assert "@biomcp" in res.output or "@desktop-commander" in res.output


def test_profile_list_json(invoke):
    """Test profile list JSON output."""
    res = invoke(["profile", "list", "--format", "json"])
    assert res.exit_code == 0
    data = json.loads(res.output)

    # Check structure - at least one HTTP profile should exist
    assert "@testapi/users" in data

    # Check HTTP profile structure
    users = data["@testapi/users"]
    assert users["type"] == "http"
    assert users["namespace"] == "testapi"
    assert users["name"] == "users"
    assert "description" in users
    assert isinstance(users["params"], list)


def test_profile_list_search(invoke):
    """Test profile search functionality."""
    res = invoke(["profile", "list", "users"])
    assert res.exit_code == 0
    # Should find profiles with "users" in name or description
    assert "@testapi/users" in res.output


def test_profile_list_type_filter(invoke):
    """Test filtering profiles by type."""
    res = invoke(["profile", "list", "--type", "http"])
    assert res.exit_code == 0
    # Should only show HTTP profiles
    assert "@testapi/users" in res.output
    assert "@testapi/projects" in res.output


def test_profile_info_http(invoke):
    """Test profile info for HTTP profile."""
    res = invoke(["profile", "info", "@testapi/users"])
    assert res.exit_code == 0
    assert "Profile: @testapi/users" in res.output
    assert "Type: HTTP" in res.output
    assert "Description:" in res.output
    assert "List users" in res.output


def test_profile_info_json(invoke):
    """Test profile info JSON output."""
    res = invoke(["profile", "info", "@testapi/users", "--format", "json"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["reference"] == "@testapi/users"
    assert data["type"] == "http"
    assert data["namespace"] == "testapi"
    assert data["name"] == "users"
    assert isinstance(data["params"], list)


def test_profile_info_not_found(invoke):
    """Test profile info for nonexistent profile."""
    res = invoke(["profile", "info", "@nonexistent/profile"])
    assert res.exit_code == 1
    assert "not found" in res.output.lower()


def test_profile_tree(invoke):
    """Test profile tree view."""
    res = invoke(["profile", "tree"])
    assert res.exit_code == 0
    assert "profiles/" in res.output
    assert "http/" in res.output
    assert "testapi/" in res.output


def test_profile_tree_type_filter(invoke):
    """Test profile tree with type filter."""
    res = invoke(["profile", "tree", "--type", "http"])
    assert res.exit_code == 0
    assert "http/" in res.output
    assert "testapi/" in res.output


def test_profile_list_respects_home_flag_with_old_plugins(jn_home, invoke):
    """Profile listing should fall back to bundled inspector when custom plugin lacks support."""
    plugin_dir = jn_home / "plugins" / "databases"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    old_duckdb = plugin_dir / "duckdb_.py"
    old_duckdb.write_text(
        """#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = ["^duckdb://.*", ".*\\\\.duckdb$", "^@.*/.*"]
# role = "protocol"
# ///
import argparse
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["read", "write"])
    parser.add_argument("address", nargs="?")
    args = parser.parse_args()

    # No inspect-profiles support (simulates older plugin)
    if args.mode == "write":
        sys.stdin.read()


if __name__ == "__main__":
    main()
"""
    )

    profile_dir = jn_home / "profiles" / "duckdb" / "genie"
    profile_dir.mkdir(parents=True, exist_ok=True)

    (profile_dir / "_meta.json").write_text(
        json.dumps({"path": "folfox.duckdb"}, indent=2)
    )
    (profile_dir / "folfox-cohort.sql").write_text(
        "-- Folfox cohort\nSELECT 1;"
    )

    res = invoke(["--home", str(jn_home), "profile", "list"])
    assert res.exit_code == 0
    assert "@genie/folfox-cohort" in res.output
