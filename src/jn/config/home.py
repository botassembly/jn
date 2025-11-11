"""Plugin home resolution utilities.

Resolves plugin root and cache locations with clear precedence:
1) CLI --home argument
2) $JN_HOME environment variable
3) User config directory (XDG or ~/.config/jn)
4) Bundled defaults (jn_home) are always available via discovery fallback

This module does not perform discovery; it only tells the rest of the system
where to look for user/custom plugins and where to store cache metadata.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


@dataclass(frozen=True)
class HomePaths:
    """Resolved paths for plugin discovery and caching."""

    home_dir: Optional[Path]
    plugin_dir: Path
    cache_path: Optional[Path]


def _user_config_home() -> Path:
    """Return the user config directory for jn (XDG or ~/.config/jn)."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else (Path.home() / ".config")
    return base / "jn"


def resolve_home(home_option: Optional[str]) -> HomePaths:
    """Resolve plugin root and cache path.

    Args:
        home_option: Value of --home CLI option if provided

    Returns:
        HomePaths with home_dir (may be None), plugin_dir, cache_path
    """
    # 1) CLI --home overrides all
    if home_option:
        home_dir = Path(home_option)
        return HomePaths(
            home_dir=home_dir,
            plugin_dir=home_dir / "plugins",
            cache_path=home_dir / "cache.json",
        )

    # 2) $JN_HOME environment variable
    env_home = os.environ.get("JN_HOME")
    if env_home:
        home_dir = Path(env_home)
        return HomePaths(
            home_dir=home_dir,
            plugin_dir=home_dir / "plugins",
            cache_path=home_dir / "cache.json",
        )

    # 3) User config directory (no explicit home directory concept)
    # The directory may not exist; discovery will simply find zero custom
    # plugins and rely on bundled defaults via fallback.
    user_dir = _user_config_home()
    return HomePaths(
        home_dir=None,  # No explicit home; using user config location
        plugin_dir=user_dir / "plugins",
        cache_path=user_dir / "cache.json",
    )

