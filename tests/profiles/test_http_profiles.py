"""Tests for HTTP profile system."""
import json
import os
from pathlib import Path

import pytest

from jn.profiles.http import (
    HTTPProfile,
    ProfileError,
    find_profile_paths,
    load_profile,
    resolve_profile_reference
)


def test_find_profile_paths():
    """Test profile path discovery."""
    paths = find_profile_paths()
    assert len(paths) >= 1  # At least bundled profiles
    assert all(isinstance(p, Path) for p in paths)


def test_load_profile_jsonplaceholder():
    """Test loading bundled JSONPlaceholder profile."""
    profile = load_profile("jsonplaceholder")

    assert profile.name == "jsonplaceholder"
    assert profile.base_url == "https://jsonplaceholder.typicode.com"
    assert "Accept" in profile.headers
    assert profile.timeout == 30


def test_load_profile_not_found():
    """Test loading non-existent profile."""
    with pytest.raises(ProfileError, match="Profile not found"):
        load_profile("nonexistent-profile-xyz")


def test_profile_env_var_substitution(monkeypatch):
    """Test environment variable substitution in profiles."""
    # Create a test profile with env vars
    test_config = {
        "base_url": "https://api.example.com",
        "headers": {
            "Authorization": "Bearer ${TEST_API_TOKEN}",
            "X-Custom": "${TEST_CUSTOM_HEADER}"
        }
    }

    # Set env vars
    monkeypatch.setenv("TEST_API_TOKEN", "test-token-123")
    monkeypatch.setenv("TEST_CUSTOM_HEADER", "custom-value")

    profile = HTTPProfile("test", test_config, Path("/fake/path.json"))

    assert profile.headers["Authorization"] == "Bearer test-token-123"
    assert profile.headers["X-Custom"] == "custom-value"


def test_profile_env_var_missing(monkeypatch):
    """Test error when required env var is missing."""
    test_config = {
        "base_url": "https://api.example.com",
        "headers": {
            "Authorization": "Bearer ${MISSING_VAR}"
        }
    }

    # Make sure var is not set
    monkeypatch.delenv("MISSING_VAR", raising=False)

    profile = HTTPProfile("test", test_config, Path("/fake/path.json"))

    with pytest.raises(ProfileError, match="Environment variable MISSING_VAR not set"):
        _ = profile.headers


def test_profile_resolve_path():
    """Test path resolution with templates."""
    config = {
        "base_url": "https://api.example.com/v1",
        "paths": {
            "user": "/users/{id}",
            "repos": "/repos"
        }
    }

    profile = HTTPProfile("test", config, Path("/fake/path.json"))

    # Test simple path
    url = profile.resolve_path("/repos")
    assert url == "https://api.example.com/v1/repos"

    # Test named path with variable
    url = profile.resolve_path("user", {"id": "123"})
    assert url == "https://api.example.com/v1/users/123"


def test_resolve_profile_reference_simple():
    """Test resolving simple profile reference."""
    url, headers = resolve_profile_reference("@jsonplaceholder/users/1")

    assert url == "https://jsonplaceholder.typicode.com/users/1"
    assert "Accept" in headers
    assert headers["Accept"] == "application/json"


def test_resolve_profile_reference_no_path():
    """Test resolving profile reference without path."""
    url, headers = resolve_profile_reference("@jsonplaceholder")

    assert url == "https://jsonplaceholder.typicode.com"
    assert "Accept" in headers


def test_resolve_profile_reference_invalid():
    """Test invalid profile reference."""
    with pytest.raises(ProfileError, match="Invalid profile reference"):
        resolve_profile_reference("not-a-profile-ref")


def test_jn_cat_with_profile(invoke):
    """Test jn cat with profile reference."""
    # Skip if GITHUB_TOKEN not set (optional test)
    if not os.environ.get("GITHUB_TOKEN"):
        pytest.skip("GITHUB_TOKEN not set")

    result = invoke(["cat", "@jsonplaceholder/users/1"])

    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line]
    record = json.loads(lines[0])
    assert "id" in record
    assert record["id"] == 1


def test_jn_cat_with_profile_no_auth(invoke):
    """Test jn cat with profile that doesn't require auth."""
    result = invoke(["cat", "@jsonplaceholder/users/1"])

    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line]
    record = json.loads(lines[0])
    assert "id" in record


def test_jn_run_profile_to_csv(invoke, tmp_path):
    """Test jn run with profile reference to CSV."""
    output = tmp_path / "users.csv"

    result = invoke(["run", "@jsonplaceholder/users/1", str(output)])

    assert result.exit_code == 0
    assert output.exists()

    content = output.read_text()
    assert "id" in content.lower()
    assert "name" in content.lower()
