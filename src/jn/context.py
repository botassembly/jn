"""JN context for passing state between commands."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import click


@dataclass(frozen=True)
class HomePaths:
    """Resolved paths for plugin discovery and caching."""

    home_dir: Optional[Path]
    plugin_dir: Path
    cache_path: Optional[Path]


# Module-level cache for home resolution
_cached_home: Optional[HomePaths] = None


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
    global _cached_home

    # CLI --home overrides all (no caching when explicit)
    if home_option:
        home_dir = Path(home_option)
        return HomePaths(
            home_dir=home_dir,
            plugin_dir=home_dir / "plugins",
            cache_path=home_dir / "cache.json",
        )

    # Use cached value if available
    if _cached_home is not None:
        return _cached_home

    # $JN_HOME environment variable
    env_home = os.environ.get("JN_HOME")
    if env_home:
        home_dir = Path(env_home)
        _cached_home = HomePaths(
            home_dir=home_dir,
            plugin_dir=home_dir / "plugins",
            cache_path=home_dir / "cache.json",
        )
        return _cached_home

    # User config directory (no explicit home directory concept)
    user_dir = _user_config_home()
    _cached_home = HomePaths(
        home_dir=None,
        plugin_dir=user_dir / "plugins",
        cache_path=user_dir / "cache.json",
    )
    return _cached_home


class JNContext:
    def __init__(self):
        self.home = None
        self.plugin_dir = None
        self.cache_path = None


pass_context = click.make_pass_decorator(JNContext, ensure=True)


def get_jn_home() -> Path:
    """Get JN_HOME directory (for backward compatibility with existing code).

    Returns:
        Path to JN_HOME (either from $JN_HOME env var or default ~/.jn)
    """
    global _cached_home
    if _cached_home is None:
        _cached_home = resolve_home(None)

    # Return explicit home_dir if set, otherwise default to ~/.jn
    if _cached_home.home_dir:
        return _cached_home.home_dir
    return Path.home() / ".jn"


def get_profile_dir(profile_type: str) -> Path:
    """Get profile directory for a specific plugin type.

    Args:
        profile_type: Plugin type (e.g., "duckdb", "http", "gmail")

    Returns:
        Path to profile directory (e.g., $JN_HOME/profiles/duckdb)
    """
    return get_jn_home() / "profiles" / profile_type


def get_plugin_env() -> dict:
    """Get environment variables to pass to plugin subprocesses.

    Returns:
        Dictionary of environment variables for plugin execution
    """
    env = os.environ.copy()
    jn_home = get_jn_home()

    # Set JN environment variables
    env["JN_HOME"] = str(jn_home)
    env["JN_WORKING_DIR"] = str(Path.cwd())

    # Check if project-specific .jn directory exists
    project_dir = Path.cwd() / ".jn"
    if project_dir.exists():
        env["JN_PROJECT_DIR"] = str(project_dir)

    return env
