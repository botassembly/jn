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


def _user_config_home() -> Path:
    """Return the user config directory for jn (XDG or ~/.config/jn)."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else (Path.home() / ".config")
    return base / "jn"


def resolve_home(home_option: Optional[str]) -> HomePaths:
    """Resolve plugin root and cache path.

    Reads fresh from environment each time. Path resolution is fast (~5µs),
    so caching is unnecessary and creates fragility.

    Args:
        home_option: Value of --home CLI option if provided

    Returns:
        HomePaths with home_dir (may be None), plugin_dir, cache_path
    """
    # CLI --home overrides all
    if home_option:
        home_dir = Path(home_option)
        return HomePaths(
            home_dir=home_dir,
            plugin_dir=home_dir / "plugins",
            cache_path=home_dir / "cache.json",
        )

    # $JN_HOME environment variable
    env_home = os.environ.get("JN_HOME")
    if env_home:
        home_dir = Path(env_home)
        return HomePaths(
            home_dir=home_dir,
            plugin_dir=home_dir / "plugins",
            cache_path=home_dir / "cache.json",
        )

    # User config directory (no explicit home directory concept)
    user_dir = _user_config_home()
    return HomePaths(
        home_dir=None,
        plugin_dir=user_dir / "plugins",
        cache_path=user_dir / "cache.json",
    )


class JNContext:
    def __init__(self):
        self.home = None
        self.plugin_dir = None
        self.cache_path = None


pass_context = click.make_pass_decorator(JNContext, ensure=True)


def get_jn_home() -> Path:
    """Get JN_HOME directory.

    Reads fresh from environment each time. Fast enough for hot paths (~5µs).

    Returns:
        Path to JN_HOME (either from $JN_HOME env var or default ~/.jn)
    """
    home_paths = resolve_home(None)
    if home_paths.home_dir:
        return home_paths.home_dir
    return Path.home() / ".jn"


def get_profile_dir(profile_type: str) -> Path:
    """Get profile directory for a specific plugin type.

    Args:
        profile_type: Plugin type (e.g., "duckdb", "http", "gmail")

    Returns:
        Path to profile directory (e.g., $JN_HOME/profiles/duckdb)
    """
    return get_jn_home() / "profiles" / profile_type


def get_plugin_env(home_dir: Optional[Path] = None) -> dict:
    """Get environment variables to pass to plugin subprocesses.

    Args:
        home_dir: JN home directory (overrides $JN_HOME)

    Returns:
        Dictionary of environment variables for plugin execution
    """
    env = os.environ.copy()

    # Use provided home_dir or fall back to get_jn_home()
    jn_home = home_dir or get_jn_home()

    # Set JN environment variables
    env["JN_HOME"] = str(jn_home)
    env["JN_WORKING_DIR"] = str(Path.cwd())

    # Check if project-specific .jn directory exists
    project_dir = Path.cwd() / ".jn"
    if project_dir.exists():
        env["JN_PROJECT_DIR"] = str(project_dir)

    return env
