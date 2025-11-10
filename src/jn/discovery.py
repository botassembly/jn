"""Plugin discovery with timestamp-based caching."""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

import tomllib

# PEP 723 regex pattern
PEP723_PATTERN = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\n(?P<content>(^#(| .*)$\n)+)^# ///$"
)


@dataclass
class PluginMetadata:
    """Metadata for a discovered plugin."""

    name: str
    path: str
    mtime: float
    matches: List[str]
    requires_python: Optional[str] = None
    dependencies: List[str] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


def parse_pep723(filepath: Path) -> dict:
    """Extract PEP 723 metadata from Python file.

    Args:
        filepath: Path to Python plugin file

    Returns:
        Dict with 'dependencies', 'requires-python', and 'tool' sections
    """
    try:
        content = filepath.read_text()
    except (OSError, UnicodeDecodeError):
        return {}

    match = PEP723_PATTERN.search(content)
    if not match or match.group("type") != "script":
        return {}

    # Extract TOML content from comments
    lines = match.group("content").splitlines()
    toml_content = "\n".join(
        line[2:] if line.startswith("# ") else line[1:] for line in lines
    )

    try:
        return tomllib.loads(toml_content)
    except Exception:
        return {}


def discover_plugins(plugin_dir: Path) -> Dict[str, PluginMetadata]:
    """Discover all plugins in directory.

    Scans for .py files, extracts PEP 723 metadata.
    Stores paths RELATIVE to plugin_dir for portability.

    Args:
        plugin_dir: Directory to scan (e.g., src/jn/plugins/)

    Returns:
        Dict mapping plugin name to metadata
    """
    plugins = {}

    if not plugin_dir.exists():
        return plugins

    # Recursively find all .py files
    for py_file in plugin_dir.rglob("*.py"):
        # Skip __init__, test files
        if py_file.name in ("__init__.py", "__pycache__"):
            continue
        if py_file.name.startswith("test_"):
            continue

        # Parse PEP 723 metadata
        metadata = parse_pep723(py_file)

        # Extract plugin info
        tool_jn = metadata.get("tool", {}).get("jn", {})

        # Skip if no [tool.jn] section at all
        if not tool_jn:
            continue

        matches = tool_jn.get("matches", [])
        # Note: matches can be empty for filter plugins that don't match files
        # They're invoked by name, not by file pattern matching

        # Plugin name = filename without .py
        name = py_file.stem

        # Get file mtime
        mtime = py_file.stat().st_mtime

        # Store path RELATIVE to plugin_dir for portability
        relative_path = py_file.relative_to(plugin_dir)

        plugins[name] = PluginMetadata(
            name=name,
            path=str(relative_path),  # Relative path!
            mtime=mtime,
            matches=matches,
            requires_python=metadata.get("requires-python"),
            dependencies=metadata.get("dependencies", []),
        )

    return plugins


def load_cache(cache_path: Optional[Path]) -> dict:
    """Load plugin cache from JSON file.

    Args:
        cache_path: Path to cache.json (can be None)

    Returns:
        Cache dict with 'version', 'plugins', etc.
    """
    if cache_path is None or not cache_path.exists():
        return {"version": "0.0.1", "plugins": {}}

    try:
        with open(cache_path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"version": "0.0.1", "plugins": {}}


def save_cache(cache_path: Optional[Path], cache: dict) -> None:
    """Save plugin cache to JSON file.

    Args:
        cache_path: Path to cache.json (can be None)
        cache: Cache dict to save
    """
    if cache_path is None:
        return  # No cache path specified, skip saving
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2)


def get_cached_plugins(
    plugin_dir: Path, cache_path: Optional[Path]
) -> Dict[str, PluginMetadata]:
    """Get plugins with caching.

    Uses timestamp-based invalidation:
    - If plugin file mtime > cached mtime, re-parse
    - If plugin in cache but file deleted, remove from cache
    - If plugin file not in cache, parse and add

    Cache stores RELATIVE paths for portability across machines.

    Args:
        plugin_dir: Directory containing plugins
        cache_path: Path to cache.json (can be None)

    Returns:
        Dict mapping plugin name to metadata (with absolute paths reconstructed)
    """
    # Load cache
    cache = load_cache(cache_path)
    cached_plugins = cache.get("plugins", {})

    # Discover current plugins (returns relative paths)
    current_plugins = discover_plugins(plugin_dir)

    # Check for changes
    needs_update = False
    result = {}

    for name, meta in current_plugins.items():
        # Check if cached and up-to-date
        if name in cached_plugins:
            cached_mtime = cached_plugins[name].get("mtime", 0)
            if meta.mtime <= cached_mtime:
                # Use cached version (reconstruct absolute path)
                cached_meta = cached_plugins[name].copy()
                cached_meta["path"] = str(plugin_dir / cached_meta["path"])
                result[name] = PluginMetadata(**cached_meta)
                continue

        # New or updated plugin - convert relative path to absolute
        meta.path = str(plugin_dir / meta.path)
        result[name] = meta
        needs_update = True

    # Check for deleted plugins
    for name in cached_plugins:
        if name not in current_plugins:
            needs_update = True

    # Update cache if needed (store relative paths)
    if needs_update:
        cache["plugins"] = {}
        for name, meta in result.items():
            cache_meta = asdict(meta)
            # Convert absolute path back to relative for storage
            cache_meta["path"] = str(Path(meta.path).relative_to(plugin_dir))
            cache["plugins"][name] = cache_meta
        save_cache(cache_path, cache)

    return result


def get_plugin_by_name(
    name: str, plugins: Dict[str, PluginMetadata]
) -> Optional[PluginMetadata]:
    """Find plugin by exact name match.

    Args:
        name: Plugin name (e.g., 'csv_', 'json_')
        plugins: Plugin registry

    Returns:
        PluginMetadata or None
    """
    return plugins.get(name)


def get_cached_plugins_with_fallback(
    plugin_dir: Path, cache_path: Optional[Path], fallback_to_builtin: bool = True
) -> Dict[str, PluginMetadata]:
    """Get plugins with fallback to built-in plugins.

    Loads built-in plugins first, then merges custom plugins on top.
    Custom plugins with the same name override built-ins.

    Args:
        plugin_dir: Primary directory containing plugins
        cache_path: Path to cache.json (can be None)
        fallback_to_builtin: If True, merge with built-in plugins

    Returns:
        Dict mapping plugin name to metadata (custom plugins override built-ins)
    """
    result = {}

    # Load built-in plugins first (if fallback enabled)
    # NOTE: Built-ins are discovered without caching since:
    # 1. They never change after package installation
    # 2. There are only a few of them (fast to discover)
    # 3. We can't write to site-packages (read-only on most systems)
    if fallback_to_builtin:
        builtin_dir = Path(__file__).parent / "plugins"
        if builtin_dir.exists():
            builtin_plugins = discover_plugins(builtin_dir)
            # Convert relative paths to absolute for runtime use
            for name, meta in builtin_plugins.items():
                meta.path = str(builtin_dir / meta.path)
            result = builtin_plugins

    # Load custom/specified plugins WITH caching (override built-ins with same name)
    # Custom plugins are in user-writable directories
    custom_plugins = get_cached_plugins(plugin_dir, cache_path)
    result.update(custom_plugins)

    return result
