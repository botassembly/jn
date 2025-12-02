"""JN context for passing state between commands."""

import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Optional

import click


@dataclass(frozen=True)
class HomePaths:
    """Resolved paths for plugin discovery and caching."""

    home_dir: Optional[Path]
    plugin_dir: Path
    cache_path: Optional[Path]


def _user_global_home() -> Path:
    """Return the user global directory for jn (~/.local/jn)."""
    return Path.home() / ".local" / "jn"


def _find_project_jn_dir(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Walk up from start_dir looking for a .jn directory.

    Args:
        start_dir: Directory to start searching from (default: CWD)

    Returns:
        Path to the first .jn directory found, or None if not found.

    Resolution walks up the directory tree from start_dir until it finds
    a directory containing a .jn folder, or reaches the root directory.
    """
    current = (start_dir or Path.cwd()).resolve()

    while True:
        jn_dir = current / ".jn"
        if jn_dir.exists() and jn_dir.is_dir():
            return jn_dir

        # Stop at root directory
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def resolve_home(home_option: Optional[str]) -> HomePaths:
    """Resolve plugin root and cache path.

    Resolution order:
    1. --home CLI flag (explicit override)
    2. $JN_HOME environment variable
    3. Walk up from CWD looking for .jn directory (project-local)
    4. ~/.local/jn (user global)

    Reads fresh from environment each time. Path resolution is fast (~5µs),
    so caching is unnecessary and creates fragility.

    Args:
        home_option: Value of --home CLI option if provided

    Returns:
        HomePaths with home_dir (may be None), plugin_dir, cache_path
    """
    # 1. CLI --home overrides all
    if home_option:
        home_dir = Path(home_option)
        return HomePaths(
            home_dir=home_dir,
            plugin_dir=home_dir / "plugins",
            cache_path=home_dir / "cache.json",
        )

    # 2. $JN_HOME environment variable
    env_home = os.environ.get("JN_HOME")
    if env_home:
        home_dir = Path(env_home)
        return HomePaths(
            home_dir=home_dir,
            plugin_dir=home_dir / "plugins",
            cache_path=home_dir / "cache.json",
        )

    # 3. Walk up from CWD looking for .jn directory
    project_dir = _find_project_jn_dir()
    if project_dir:
        return HomePaths(
            home_dir=project_dir,
            plugin_dir=project_dir / "plugins",
            cache_path=project_dir / "cache.json",
        )

    # 4. User global directory (~/.local/jn)
    user_dir = _user_global_home()
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

    Resolution order:
    1. $JN_HOME environment variable
    2. Walk up from CWD looking for .jn directory
    3. ~/.local/jn (user global)

    Reads fresh from environment each time. Fast enough for hot paths (~5µs).

    Returns:
        Path to JN_HOME directory
    """
    home_paths = resolve_home(None)
    if home_paths.home_dir:
        return home_paths.home_dir
    # Fall back to user global directory
    return _user_global_home()


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

    Ensures plugins see the same JN_HOME context as the main process by
    propagating the resolved home directory.

    Args:
        home_dir: JN home directory (overrides resolution)

    Returns:
        Dictionary of environment variables for plugin execution
    """
    env = os.environ.copy()

    # Use provided home_dir or fall back to get_jn_home()
    # This ensures plugins see the same resolved JN_HOME
    jn_home = home_dir or get_jn_home()

    # Set JN environment variables
    env["JN_HOME"] = str(jn_home)
    env["JN_WORKING_DIR"] = str(Path.cwd())

    # Find project directory using walk-up logic (may be in parent dir)
    project_dir = _find_project_jn_dir()
    if project_dir:
        env["JN_PROJECT_DIR"] = str(project_dir)

    return env


def get_builtin_plugins_dir() -> Optional[Path]:
    """Locate the packaged default plugins under jn_home.plugins.

    Returns:
        Path to the bundled plugins directory, or None if not found.
    """
    try:
        pkg = resources.files("jn_home").joinpath("plugins")
        with resources.as_file(pkg) as p:
            return Path(p)
    except (ModuleNotFoundError, TypeError):
        return None


def get_binary_plugins_dir() -> Optional[Path]:
    """Locate the binary plugins directory (Zig, Rust, etc.).

    Resolution order:
    1. $JN_HOME/plugins/ if JN_HOME is set
    2. plugins/ relative to repo root (development)
    3. Installed alongside the package

    Returns:
        Path to the binary plugins directory, or None if not found.
    """
    # Check JN_HOME first
    jn_home = os.environ.get("JN_HOME")
    if jn_home:
        plugins_dir = Path(jn_home) / "plugins"
        if plugins_dir.exists():
            return plugins_dir

    # Check relative to this file (development mode)
    # context.py is at src/jn/context.py, so repo root is 3 levels up
    context_file = Path(__file__)
    repo_root = context_file.parent.parent.parent
    plugins_dir = repo_root / "plugins"
    if plugins_dir.exists() and (plugins_dir / "zig").exists():
        return plugins_dir

    return None
