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
    """Test profile path discovery returns valid Path objects."""
    paths = find_profile_paths()
    # HTTP profiles are optional (may be empty if none bundled and none in user dir)
    assert isinstance(paths, list)
    assert all(isinstance(p, Path) for p in paths)


def test_resolve_profile_reference_invalid():
    """Test invalid profile reference."""
    with pytest.raises(ProfileError, match="Invalid profile reference"):
        resolve_profile_reference("not-a-profile-ref")
