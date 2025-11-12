"""Plugin business logic and introspection (service façade)."""

import io
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .discovery import (
    PluginMetadata,
    get_cached_plugins_with_fallback,
)
from ..cli.helpers import build_subprocess_env_for_coverage


def _check_uv_available() -> None:
    """Check if UV is available and exit with helpful message if not."""
    if not shutil.which("uv"):
        print("Error: UV is required to run JN plugins", file=sys.stderr)
        print("", file=sys.stderr)
        print("Install UV with one of these methods:", file=sys.stderr)
        print(
            "  curl -LsSf https://astral.sh/uv/install.sh | sh",
            file=sys.stderr,
        )
        print("  pip install uv", file=sys.stderr)
        print("", file=sys.stderr)
        print("More info: https://docs.astral.sh/uv/", file=sys.stderr)
        sys.exit(1)


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
            lines = match.group(1).strip().split("\n")
            return lines[0].strip() if lines else ""
    return ""


def detect_plugin_methods(plugin_path: str) -> List[str]:
    """Detect which methods a plugin implements."""
    with open(plugin_path) as f:
        content = f.read()
        methods: List[str] = []
        if re.search(r"^def reads\(", content, re.MULTILINE):
            methods.append("reads")
        if re.search(r"^def writes\(", content, re.MULTILINE):
            methods.append("writes")
        if re.search(r"^def filters\(", content, re.MULTILINE):
            methods.append("filters")
        if re.search(r"^def test\(", content, re.MULTILINE):
            methods.append("test")
        return methods


def extract_method_docstring(plugin_path: str, method_name: str) -> str:
    """Extract first line of method docstring."""
    with open(plugin_path) as f:
        content = f.read()
        pattern = rf'^def {method_name}\([^)]*\):[^"]*"""([^"]+)"""'
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        if match:
            return match.group(1).strip().split("\n")[0]
    return ""


def infer_plugin_type(methods: List[str]) -> str:
    """Infer plugin type from available methods."""
    has_reads = "reads" in methods
    has_writes = "writes" in methods
    has_filters = "filters" in methods

    if has_reads and has_writes:
        return "format"
    elif has_filters:
        return "filter"
    elif has_reads:
        return "protocol"
    else:
        return "unknown"


def get_plugin_info(
    plugin_name: str, plugin_meta: PluginMetadata
) -> "PluginInfo":
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


def list_plugins(
    plugin_dir: Path, cache_path: Optional[Path]
) -> Dict[str, PluginInfo]:
    """List all available plugins with their information."""
    plugins = get_cached_plugins_with_fallback(plugin_dir, cache_path)
    result: Dict[str, PluginInfo] = {}
    for name, meta in plugins.items():
        result[name] = get_plugin_info(name, meta)
    return result


def find_plugin(
    plugin_name: str, plugin_dir: Path, cache_path: Optional[Path]
) -> Optional[PluginInfo]:
    """Find a specific plugin by name."""
    plugins = get_cached_plugins_with_fallback(plugin_dir, cache_path)
    if plugin_name not in plugins:
        return None
    return get_plugin_info(plugin_name, plugins[plugin_name])


def call_plugin(plugin_path: str, args: List[str]) -> int:
    """Call a plugin directly with arguments, piping stdin if needed."""
    # Check UV availability first
    _check_uv_available()

    # Try to pass through current stdin; if it's not a real file (e.g., Click runner),
    # use PIPE and feed the input content explicitly.
    try:
        sys.stdin.fileno()  # type: ignore[attr-defined]
        stdin_source = sys.stdin.buffer  # Always use binary mode for stdin
        input_data = None
    except (AttributeError, OSError, io.UnsupportedOperation):
        # Not a real file handle (e.g., Click test runner StringIO/BytesIO)
        stdin_source = subprocess.PIPE
        input_data = sys.stdin.read()

    # Always use binary mode for the subprocess
    # This allows plugins to output either text (NDJSON) or binary (XLSX, PDF, etc.)
    proc = subprocess.Popen(
        ["uv", "run", "--script", plugin_path, *args],
        stdin=stdin_source,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,  # Binary mode for both stdin and stdout
        env=build_subprocess_env_for_coverage(),
    )
    if input_data is not None:
        # Encode input data if it's a string
        if isinstance(input_data, str):
            proc.stdin.write(input_data.encode("utf-8"))  # type: ignore[union-attr]
        else:
            proc.stdin.write(input_data)  # type: ignore[union-attr]
        proc.stdin.close()  # type: ignore[union-attr]

    # Pipe plugin stdout to our stdout
    # Output may be text (NDJSON from read mode) or binary (XLSX from write mode)
    assert proc.stdout is not None
    while True:
        chunk = proc.stdout.read(8192)
        if not chunk:
            break
        sys.stdout.buffer.write(chunk)  # type: ignore[attr-defined]

    proc.wait()

    # Forward any stderr produced by the plugin to the caller's stderr
    if proc.stderr is not None:
        try:
            err_data = proc.stderr.read()
            if err_data:
                # Ensure bytes go to a binary-capable stream
                sys.stderr.buffer.write(err_data)  # type: ignore[attr-defined]
                sys.stderr.buffer.flush()  # type: ignore[attr-defined]
        except Exception:
            pass

    return proc.returncode
