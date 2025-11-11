"""Tests for HTTP profile system."""
import json
import os
from pathlib import Path

import pytest

from jn.profiles.http import (
    ProfileError,
    find_profile_paths,
    resolve_profile_reference
)


def test_find_profile_paths():
    """Test profile path discovery."""
    paths = find_profile_paths()
    assert len(paths) >= 1  # At least bundled profiles
    assert all(isinstance(p, Path) for p in paths)


@pytest.mark.skip(reason="HTTPProfile class removed - hierarchical profiles now used")
def test_load_profile_jsonplaceholder():
    """Test loading bundled JSONPlaceholder profile."""
    pass


@pytest.mark.skip(reason="HTTPProfile class removed - hierarchical profiles now used")
def test_load_profile_not_found():
    """Test loading non-existent profile."""
    pass


@pytest.mark.skip(reason="HTTPProfile class removed - hierarchical profiles now used")
def test_profile_env_var_substitution(monkeypatch):
    """Test environment variable substitution in profiles."""
    pass


@pytest.mark.skip(reason="HTTPProfile class removed - hierarchical profiles now used")
def test_profile_env_var_missing(monkeypatch):
    """Test error when required env var is missing."""
    pass


@pytest.mark.skip(reason="HTTPProfile class removed - hierarchical profiles now used")
def test_profile_resolve_path():
    """Test path resolution with templates."""
    pass


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


def test_parameter_validation_warning(capsys):
    """Test that warnings are shown for unsupported parameters."""
    # Skip if genomoncology env vars not set
    if not os.environ.get("GENOMONCOLOGY_URL"):
        pytest.skip("GENOMONCOLOGY_URL not set")

    # This should trigger a warning for unsupported parameters
    params = {
        "gene": "EGFR",
        "mutation_type_group": "Insertion",  # Not supported
        "invalid_param": "test"  # Also not supported
    }

    # Call resolve_profile_reference
    url, headers = resolve_profile_reference("@genomoncology/alterations", params)

    # Check that URL was still built (non-blocking warning)
    assert "alterations" in url
    assert "gene=EGFR" in url
    assert "mutation_type_group=Insertion" in url

    # Check stderr output for warning
    captured = capsys.readouterr()
    assert "Warning:" in captured.err
    assert "mutation_type_group" in captured.err or "invalid_param" in captured.err
    assert "Supported parameters:" in captured.err
