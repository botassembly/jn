"""Tests for HTTP profile system."""
import json
import os
from pathlib import Path

import pytest

from jn.profiles.http import (
    ProfileError,
    find_profile_paths,
    load_hierarchical_profile,
    resolve_profile_reference,
    substitute_env_vars
)


def test_find_profile_paths():
    """Test profile path discovery."""
    paths = find_profile_paths()
    assert len(paths) >= 1  # At least bundled profiles
    assert all(isinstance(p, Path) for p in paths)


def test_load_hierarchical_profile_genomoncology():
    """Test loading bundled GenomOncology profile."""
    # Load just _meta.json
    profile = load_hierarchical_profile("genomoncology")

    assert "base_url" in profile
    assert "headers" in profile

    # Load _meta + source
    profile = load_hierarchical_profile("genomoncology", "annotations")
    assert "base_url" in profile
    assert "path" in profile


def test_load_hierarchical_profile_not_found():
    """Test loading non-existent profile."""
    with pytest.raises(ProfileError, match="Profile not found"):
        load_hierarchical_profile("nonexistent-profile-xyz")


def test_profile_env_var_substitution(monkeypatch):
    """Test environment variable substitution."""
    # Set env vars
    monkeypatch.setenv("TEST_API_TOKEN", "test-token-123")
    monkeypatch.setenv("TEST_CUSTOM_HEADER", "custom-value")

    # Test substitution
    result = substitute_env_vars("Bearer ${TEST_API_TOKEN}")
    assert result == "Bearer test-token-123"

    result = substitute_env_vars("${TEST_CUSTOM_HEADER}")
    assert result == "custom-value"


def test_profile_env_var_missing(monkeypatch):
    """Test error when required env var is missing."""
    # Make sure var is not set
    monkeypatch.delenv("MISSING_VAR", raising=False)

    with pytest.raises(ProfileError, match="Environment variable MISSING_VAR not set"):
        substitute_env_vars("Bearer ${MISSING_VAR}")


def test_resolve_profile_reference_with_source(monkeypatch):
    """Test resolving profile reference with source."""
    monkeypatch.setenv("GENOMONCOLOGY_URL", "example.genomoncology.com")
    monkeypatch.setenv("GENOMONCOLOGY_API_KEY", "test-key-123")

    url, headers = resolve_profile_reference("@genomoncology/annotations")

    assert url.startswith("https://")
    assert "annotations" in url
    assert isinstance(headers, dict)
    assert "Authorization" in headers


def test_resolve_profile_reference_just_api(monkeypatch):
    """Test resolving profile reference without source."""
    monkeypatch.setenv("GENOMONCOLOGY_URL", "example.genomoncology.com")
    monkeypatch.setenv("GENOMONCOLOGY_API_KEY", "test-key-123")

    url, headers = resolve_profile_reference("@genomoncology")

    assert url.startswith("https://")
    assert isinstance(headers, dict)


def test_resolve_profile_reference_invalid():
    """Test invalid profile reference."""
    with pytest.raises(ProfileError, match="Invalid profile reference"):
        resolve_profile_reference("not-a-profile-ref")


def test_resolve_profile_reference_with_params(monkeypatch):
    """Test resolving profile reference with query params."""
    monkeypatch.setenv("GENOMONCOLOGY_URL", "example.genomoncology.com")
    monkeypatch.setenv("GENOMONCOLOGY_API_KEY", "test-key-123")

    url, headers = resolve_profile_reference("@genomoncology/annotations", params={"gene": "BRAF"})

    assert url.startswith("https://")
    assert "gene=BRAF" in url
    assert isinstance(headers, dict)
