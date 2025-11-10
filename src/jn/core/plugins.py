"""Plugin business logic and introspection."""

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from ..discovery import PluginMetadata, get_cached_plugins_with_fallback, parse_pep723


@dataclass
class PluginInfo:
    """Rich plugin information for display."""

    name: str
    path: str
    plugin_type: str
    description: str
    methods: List[str]
    matches: List[str]
    dependencies: List[str]
    requires_python: Optional[str]
    method_docs: Dict[str, str]


def extract_description(plugin_path: str) -> str:
    """Extract plugin description from module docstring.

    Args:
        plugin_path: Path to plugin file

    Returns:
        First line of module docstring or empty string
    """
    try:
        with open(plugin_path) as f:
            content = f.read()
            # Match module docstring
            match = re.search(r'"""(.+?)"""', content, re.DOTALL)
            if match:
                # Get first non-empty line
                lines = match.group(1).strip().split('\n')
                return lines[0].strip() if lines else ""
    except Exception:
        pass
    return ""


def detect_plugin_methods(plugin_path: str) -> List[str]:
    """Detect which methods a plugin implements.

    Args:
        plugin_path: Path to plugin file

    Returns:
        List of method names (reads, writes, filters, test)
    """
    try:
        with open(plugin_path) as f:
            content = f.read()
            methods = []
            if re.search(r'^def reads\(', content, re.MULTILINE):
                methods.append('reads')
            if re.search(r'^def writes\(', content, re.MULTILINE):
                methods.append('writes')
            if re.search(r'^def filters\(', content, re.MULTILINE):
                methods.append('filters')
            if re.search(r'^def test\(', content, re.MULTILINE):
                methods.append('test')
            return methods
    except Exception:
        return []


def extract_method_docstring(plugin_path: str, method_name: str) -> str:
    """Extract first line of method docstring.

    Args:
        plugin_path: Path to plugin file
        method_name: Name of method (e.g., 'reads', 'writes')

    Returns:
        First line of docstring or empty string
    """
    try:
        with open(plugin_path) as f:
            content = f.read()
            pattern = rf'^def {method_name}\([^)]*\):[^"]*"""([^"]+)"""'
            match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
            if match:
                return match.group(1).strip().split('\n')[0]
    except Exception:
        pass
    return ""


def infer_plugin_type(methods: List[str]) -> str:
    """Infer plugin type from available methods.

    Args:
        methods: List of method names

    Returns:
        Plugin type: format, filter, protocol, or unknown
    """
    has_reads = 'reads' in methods
    has_writes = 'writes' in methods
    has_filters = 'filters' in methods

    if has_reads and has_writes:
        return 'format'
    elif has_filters:
        return 'filter'
    elif has_reads:
        return 'protocol'
    else:
        return 'unknown'


def get_plugin_info(
    plugin_name: str,
    plugin_meta: PluginMetadata
) -> PluginInfo:
    """Get detailed plugin information.

    Args:
        plugin_name: Plugin name
        plugin_meta: Plugin metadata from discovery

    Returns:
        PluginInfo with all details
    """
    description = extract_description(plugin_meta.path)
    methods = detect_plugin_methods(plugin_meta.path)
    plugin_type = infer_plugin_type(methods)

    # Extract method docstrings
    method_docs = {}
    for method in methods:
        doc = extract_method_docstring(plugin_meta.path, method)
        if doc:
            method_docs[method] = doc

    return PluginInfo(
        name=plugin_name,
        path=plugin_meta.path,
        plugin_type=plugin_type,
        description=description,
        methods=methods,
        matches=plugin_meta.matches,
        dependencies=plugin_meta.dependencies or [],
        requires_python=plugin_meta.requires_python,
        method_docs=method_docs,
    )


def list_plugins(
    plugin_dir: Path,
    cache_path: Optional[Path]
) -> Dict[str, PluginInfo]:
    """List all available plugins with their information.

    Args:
        plugin_dir: Directory containing plugins
        cache_path: Path to cache file

    Returns:
        Dict mapping plugin name to PluginInfo
    """
    plugins = get_cached_plugins_with_fallback(plugin_dir, cache_path)

    result = {}
    for name, meta in plugins.items():
        result[name] = get_plugin_info(name, meta)

    return result


def find_plugin(
    plugin_name: str,
    plugin_dir: Path,
    cache_path: Optional[Path]
) -> Optional[PluginInfo]:
    """Find a specific plugin by name.

    Args:
        plugin_name: Name of plugin to find
        plugin_dir: Directory containing plugins
        cache_path: Path to cache file

    Returns:
        PluginInfo if found, None otherwise
    """
    plugins = get_cached_plugins_with_fallback(plugin_dir, cache_path)

    if plugin_name not in plugins:
        return None

    return get_plugin_info(plugin_name, plugins[plugin_name])


def run_plugin_test(
    plugin_path: str,
    capture_output: bool = False
) -> subprocess.CompletedProcess:
    """Run a plugin's self-test.

    Args:
        plugin_path: Path to plugin file
        capture_output: Whether to capture stdout/stderr

    Returns:
        CompletedProcess result
    """
    return subprocess.run(
        [sys.executable, plugin_path, '--test'],
        capture_output=capture_output,
        text=True if capture_output else False
    )


def call_plugin(
    plugin_path: str,
    args: List[str]
) -> int:
    """Call a plugin directly with arguments.

    Args:
        plugin_path: Path to plugin file
        args: Arguments to pass to plugin

    Returns:
        Plugin exit code
    """
    cmd = [sys.executable, plugin_path, *args]
    proc = subprocess.Popen(cmd)
    proc.wait()
    return proc.returncode
