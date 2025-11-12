"""Tests for HTTP profile system."""

import os
from pathlib import Path

import pytest

from jn.profiles.http import (
    ProfileError,
    find_profile_paths,
    resolve_profile_reference,
)


def test_find_profile_paths():
    """Test profile path discovery."""
    paths = find_profile_paths()
    assert len(paths) >= 1  # At least bundled profiles
    assert all(isinstance(p, Path) for p in paths)


def test_resolve_profile_reference_invalid():
    """Test invalid profile reference."""
    with pytest.raises(ProfileError, match="Invalid profile reference"):
        resolve_profile_reference("not-a-profile-ref")


def test_parameter_validation_warning_via_cli(invoke):
    """Test parameter validation warning via CLI."""
    if not os.environ.get("GENOMONCOLOGY_URL"):
        pytest.skip("GENOMONCOLOGY_URL not set")

    # Pass unsupported parameter via CLI
    result = invoke(
        [
            "cat",
            "@genomoncology/alterations",
            "-p",
            "gene=EGFR",
            "-p",
            "mutation_type_group=Insertion",  # Not supported
        ]
    )

    # Command should still work (non-blocking warning)
    assert result.exit_code == 0

    # Check that warning appeared in stderr
    assert "Warning:" in result.stderr
    assert "mutation_type_group" in result.stderr
    assert "Supported parameters:" in result.stderr


def test_parameter_validation_with_valid_params(invoke):
    """Test that valid parameters don't trigger warnings."""
    if not os.environ.get("GENOMONCOLOGY_URL"):
        pytest.skip("GENOMONCOLOGY_URL not set")

    result = invoke(
        [
            "cat",
            "@genomoncology/alterations",
            "-p",
            "gene=EGFR",
            "-p",
            "limit=5",
        ]
    )

    # Should work without warnings
    assert result.exit_code == 0
    assert "Warning:" not in result.stderr
