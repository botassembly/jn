"""Plugin discovery with timestamp-based caching (logic module)."""

import json
import re
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
) -> Dict[str, PluginMetadata]:
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
    return result


def get_plugin_by_name(
    name: str, plugins: Dict[str, PluginMetadata]
) -> Optional[PluginMetadata]:
    """Find plugin by exact name match in a mapping."""
    return plugins.get(name)
