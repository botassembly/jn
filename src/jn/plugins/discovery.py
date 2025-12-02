"""Plugin discovery with timestamp-based caching (logic module)."""

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

import tomllib

from ..context import get_builtin_plugins_dir

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
    role: Optional[str] = None
    supports_raw: bool = False
    manages_parameters: bool = False  # Plugin handles own parameter parsing
    supports_container: bool = False  # Plugin supports container inspection
    container_mode: Optional[str] = None  # e.g., "path_count", "query_param"
    is_binary: bool = False  # True for native binary plugins (Zig, Rust, etc.)
    modes: List[str] = None  # Supported modes (read, write) - None means all

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


def parse_pep723(filepath: Path) -> dict:
    """Extract PEP 723 metadata from Python file."""
    try:
        content = filepath.read_text()
    except (OSError, UnicodeDecodeError):
        return {}

    match = PEP723_PATTERN.search(content)
    if not match or match.group("type") != "script":
        return {}

    lines = match.group("content").splitlines()
    toml_content = "\n".join(
        line[2:] if line.startswith("# ") else line[1:] for line in lines
    )

    try:
        return tomllib.loads(toml_content)
    except tomllib.TOMLDecodeError:
        # Can't parse - return empty dict so discovery continues
        return {}


def discover_plugins(plugin_dir: Path) -> Dict[str, PluginMetadata]:
    """Discover all plugins in a directory (relative paths in metadata)."""
    plugins: Dict[str, PluginMetadata] = {}
    if not plugin_dir or not plugin_dir.exists():
        return plugins

    for py_file in plugin_dir.rglob("*.py"):
        if py_file.name in ("__init__.py", "__pycache__"):
            continue
        if py_file.name.startswith("test_"):
            continue

        metadata = parse_pep723(py_file)
        tool_jn = metadata.get("tool", {}).get("jn", {})
        matches = tool_jn.get("matches", [])

        # Allow empty matches (filters invoked by name)
        name = py_file.stem
        mtime = py_file.stat().st_mtime
        relative_path = py_file.relative_to(plugin_dir)

        # Infer role from relative path (protocols/, formats/, filters/)
        rel_str = str(relative_path).replace("\\", "/")
        parts = rel_str.split("/")

        # Check if role is explicitly set in metadata, otherwise infer from directory
        role = tool_jn.get("role")
        if not role:
            if "protocols" in parts:
                role = "protocol"
            elif "formats" in parts:
                role = "format"
            elif "filters" in parts:
                role = "filter"

        supports_raw = bool(tool_jn.get("supports_raw", False))
        manages_parameters = bool(tool_jn.get("manages_parameters", False))
        supports_container = bool(tool_jn.get("supports_container", False))
        container_mode = tool_jn.get("container_mode")

        plugins[name] = PluginMetadata(
            name=name,
            path=str(relative_path),
            mtime=mtime,
            matches=matches,
            requires_python=metadata.get("requires-python"),
            dependencies=metadata.get("dependencies", []),
            role=role,
            supports_raw=supports_raw,
            manages_parameters=manages_parameters,
            supports_container=supports_container,
            container_mode=container_mode,
        )

    return plugins


def _get_binary_metadata(binary: Path) -> Optional[PluginMetadata]:
    """Get metadata from a binary plugin via --jn-meta.

    Args:
        binary: Path to executable binary

    Returns:
        PluginMetadata if binary responds properly, None otherwise
    """
    if not binary.is_file() or not os.access(binary, os.X_OK):
        return None

    try:
        result = subprocess.run(  # noqa: S603  # jn:ignore[subprocess_capture_output]
            [str(binary), "--jn-meta"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        meta = json.loads(result.stdout.strip())
        name = meta.get("name", binary.name)
        matches = meta.get("matches", [])
        role = meta.get("role", "format")
        mtime = binary.stat().st_mtime

        return PluginMetadata(
            name=name,
            path=str(binary),
            mtime=mtime,
            matches=matches,
            role=role,
            is_binary=True,
            modes=meta.get("modes"),
        )
    except (
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        OSError,
    ):
        return None


def discover_binary_plugins(binary_dir: Path) -> Dict[str, PluginMetadata]:
    """Discover native binary plugins (Zig, Rust, etc.) via --jn-meta.

    Binary plugins must:
    1. Be executable files
    2. Respond to --jn-meta with JSON metadata containing:
       - name: plugin name
       - matches: list of regex patterns
       - role: plugin role (format, filter, protocol)
       - modes: list of supported modes
       - version (optional): plugin version
    """
    plugins: Dict[str, PluginMetadata] = {}
    if not binary_dir or not binary_dir.exists():
        return plugins

    # Look for Zig plugins in plugins/zig/*/bin/*
    zig_dir = binary_dir / "zig"
    if zig_dir.exists():
        for plugin_dir in zig_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            bin_dir = plugin_dir / "bin"
            if not bin_dir.exists():
                continue

            for binary in bin_dir.iterdir():
                meta = _get_binary_metadata(binary)
                if meta:
                    plugins[meta.name] = meta

    return plugins


def discover_zig_plugins_with_build() -> Dict[str, PluginMetadata]:
    """Discover Zig plugins, building from source if needed.

    This function:
    1. Lists available Zig plugin sources
    2. Builds binaries on-demand using zig_builder
    3. Returns metadata for successfully built plugins

    This enables cross-platform installation via `uv pip install` by
    compiling native binaries from bundled Zig sources on first use.

    Returns:
        Dictionary of plugin name -> PluginMetadata
    """
    plugins: Dict[str, PluginMetadata] = {}

    try:
        from ..zig_builder import (
            get_or_build_plugin,
            list_available_zig_plugins,
        )

        for plugin_name in list_available_zig_plugins():
            binary_path = get_or_build_plugin(plugin_name)
            if binary_path:
                meta = _get_binary_metadata(binary_path)
                if meta:
                    plugins[meta.name] = meta

    except ImportError:
        # zig_builder not available
        pass

    return plugins


def load_cache(cache_path: Optional[Path]) -> dict:
    if cache_path is None or not cache_path.exists():
        return {"version": "0.0.1", "plugins": {}}
    try:
        with open(cache_path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"version": "0.0.1", "plugins": {}}


def save_cache(cache_path: Optional[Path], cache: dict) -> None:
    if cache_path is None:
        return
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2)


def get_cached_plugins(
    plugin_dir: Path, cache_path: Optional[Path]
) -> Dict[str, PluginMetadata]:
    cache = load_cache(cache_path)
    cached_plugins = cache.get("plugins", {})
    current_plugins = discover_plugins(plugin_dir)

    needs_update = False
    result: Dict[str, PluginMetadata] = {}

    for name, meta in current_plugins.items():
        if name in cached_plugins:
            cached_mtime = cached_plugins[name].get("mtime", 0)
            if meta.mtime <= cached_mtime:
                cached_meta = cached_plugins[name].copy()
                cached_meta["path"] = str(plugin_dir / cached_meta["path"])
                result[name] = PluginMetadata(**cached_meta)
                continue

        meta.path = str(plugin_dir / meta.path)
        result[name] = meta
        needs_update = True

    for name in cached_plugins:
        if name not in current_plugins:
            needs_update = True

    if needs_update:
        cache["plugins"] = {}
        for name, meta in result.items():
            cache_meta = asdict(meta)
            cache_meta["path"] = str(Path(meta.path).relative_to(plugin_dir))
            cache["plugins"][name] = cache_meta
        save_cache(cache_path, cache)

    return result


def _builtin_plugins_dir() -> Optional[Path]:
    """Locate the packaged default plugins under jn_home.plugins.

    Deprecated: Use get_builtin_plugins_dir() from jn.context instead.
    """
    return get_builtin_plugins_dir()


def get_cached_plugins_with_fallback(
    plugin_dir: Path,
    cache_path: Optional[Path],
    fallback_to_builtin: bool = True,
    binary_plugins_dir: Optional[Path] = None,
    build_zig_plugins: bool = True,
) -> Dict[str, PluginMetadata]:
    """Discover all plugins with fallback to built-in plugins.

    Args:
        plugin_dir: Custom plugin directory
        cache_path: Path to cache file
        fallback_to_builtin: Include built-in Python plugins
        binary_plugins_dir: Directory containing binary plugins (e.g., plugins/zig/)
                           If None, binary plugins are not discovered.
        build_zig_plugins: Build Zig plugins from source if not already compiled.
                          This enables cross-platform installation via `uv pip install`.

    Returns:
        Dictionary of plugin name -> PluginMetadata
    """
    result: Dict[str, PluginMetadata] = {}

    if fallback_to_builtin:
        builtin_dir = get_builtin_plugins_dir()
        if builtin_dir and builtin_dir.exists():
            builtin_plugins = discover_plugins(builtin_dir)
            for _name, meta in builtin_plugins.items():
                meta.path = str(builtin_dir / meta.path)
            result = builtin_plugins

    custom_plugins = get_cached_plugins(plugin_dir, cache_path)
    result.update(custom_plugins)

    # Discover binary plugins (Zig, Rust, etc.) if directory provided
    # Binary plugins take precedence over Python plugins with same name
    if binary_plugins_dir:
        binary_plugins = discover_binary_plugins(binary_plugins_dir)
        result.update(binary_plugins)

    # Build Zig plugins from source if enabled (on-demand compilation)
    # This enables `uv pip install jn-cli` to work on all platforms
    if build_zig_plugins:
        zig_plugins = discover_zig_plugins_with_build()
        result.update(zig_plugins)

    return result


def get_plugin_by_name(
    name: str, plugins: Dict[str, PluginMetadata]
) -> Optional[PluginMetadata]:
    """Find plugin by exact name match in a mapping."""
    return plugins.get(name)
