"""Plugin business logic and introspection (service façade)."""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import io

from .discovery import (
    PluginMetadata,
    get_cached_plugins_with_fallback,
    parse_pep723,
)
import re


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
    """Extract plugin description from module docstring."""
    with open(plugin_path) as f:
        content = f.read()
        match = re.search(r'"""(.+?)"""', content, re.DOTALL)
        if match:
            lines = match.group(1).strip().split('\n')
            return lines[0].strip() if lines else ""
    return ""


def detect_plugin_methods(plugin_path: str) -> List[str]:
    """Detect which methods a plugin implements."""
    with open(plugin_path) as f:
        content = f.read()
        methods: List[str] = []
        if re.search(r'^def reads\(', content, re.MULTILINE):
            methods.append('reads')
        if re.search(r'^def writes\(', content, re.MULTILINE):
            methods.append('writes')
        if re.search(r'^def filters\(', content, re.MULTILINE):
            methods.append('filters')
        if re.search(r'^def test\(', content, re.MULTILINE):
            methods.append('test')
        return methods


def extract_method_docstring(plugin_path: str, method_name: str) -> str:
    """Extract first line of method docstring."""
    with open(plugin_path) as f:
        content = f.read()
        pattern = rf'^def {method_name}\([^)]*\):[^"]*"""([^"]+)"""'
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        if match:
            return match.group(1).strip().split('\n')[0]
    return ""


def infer_plugin_type(methods: List[str]) -> str:
    """Infer plugin type from available methods."""
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


def get_plugin_info(plugin_name: str, plugin_meta: PluginMetadata) -> 'PluginInfo':
    """Get detailed plugin information."""
    description = extract_description(plugin_meta.path)
    methods = detect_plugin_methods(plugin_meta.path)
    plugin_type = infer_plugin_type(methods)

    method_docs: Dict[str, str] = {}
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


def list_plugins(plugin_dir: Path, cache_path: Optional[Path]) -> Dict[str, PluginInfo]:
    """List all available plugins with their information."""
    plugins = get_cached_plugins_with_fallback(plugin_dir, cache_path)
    result: Dict[str, PluginInfo] = {}
    for name, meta in plugins.items():
        result[name] = get_plugin_info(name, meta)
    return result


def find_plugin(plugin_name: str, plugin_dir: Path, cache_path: Optional[Path]) -> Optional[PluginInfo]:
    """Find a specific plugin by name."""
    plugins = get_cached_plugins_with_fallback(plugin_dir, cache_path)
    if plugin_name not in plugins:
        return None
    return get_plugin_info(plugin_name, plugins[plugin_name])


def call_plugin(plugin_path: str, args: List[str]) -> int:
    """Call a plugin directly with arguments, piping stdin if needed."""
    # Try to pass through current stdin; if it's not a real file (e.g., Click runner),
    # use PIPE and feed the input content explicitly.
    try:
        sys.stdin.fileno()  # type: ignore[attr-defined]
        stdin_source = sys.stdin
        input_data = None
        text_mode = False
    except (AttributeError, OSError, io.UnsupportedOperation):
        # Not a real file handle (e.g., Click test runner StringIO)
        stdin_source = subprocess.PIPE
        input_data = sys.stdin.read()
        text_mode = True if isinstance(input_data, str) else False

    proc = subprocess.Popen(
        [sys.executable, plugin_path, *args],
        stdin=stdin_source,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if input_data is not None:
        proc.stdin.write(input_data)  # type: ignore[union-attr]
        proc.stdin.close()  # type: ignore[union-attr]

    # Pipe plugin stdout to our stdout so Click runner captures it
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)

    proc.wait()
    return proc.returncode
