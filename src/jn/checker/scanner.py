"""File scanner for finding plugins to check."""

from pathlib import Path
from typing import List


def find_plugin_files(plugin_dir: Path) -> List[Path]:
    """Find all plugin files in a directory.

    Args:
        plugin_dir: Directory to scan

    Returns:
        List of plugin file paths
    """
    if not plugin_dir or not plugin_dir.exists():
        return []

    plugins = []
    for py_file in plugin_dir.rglob("*.py"):
        # Skip special files
        if py_file.name in ("__init__.py", "__pycache__"):
            continue
        if py_file.name.startswith("test_"):
            continue
        if "/__pycache__/" in str(py_file):
            continue

        plugins.append(py_file)

    return sorted(plugins)


def find_core_files(core_dir: Path) -> List[Path]:
    """Find all core framework files.

    Args:
        core_dir: Core source directory (e.g., src/jn)

    Returns:
        List of core file paths
    """
    if not core_dir or not core_dir.exists():
        return []

    files = []
    for py_file in core_dir.rglob("*.py"):
        # Skip test files and cache
        if py_file.name.startswith("test_"):
            continue
        if "/__pycache__/" in str(py_file):
            continue

        files.append(py_file)

    return sorted(files)


def find_single_plugin(plugin_name: str, search_dirs: List[Path]) -> Path:
    """Find a specific plugin by name.

    Args:
        plugin_name: Plugin name (e.g., 'csv_' or 'csv')
        search_dirs: Directories to search

    Returns:
        Path to plugin file

    Raises:
        FileNotFoundError: If plugin not found
    """
    # Try exact match first
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        candidate = search_dir / f"{plugin_name}.py"
        if candidate.exists():
            return candidate

        # Also search recursively
        for py_file in search_dir.rglob(f"{plugin_name}.py"):
            return py_file

    # Try without underscore suffix
    if not plugin_name.endswith("_"):
        return find_single_plugin(f"{plugin_name}_", search_dirs)

    raise FileNotFoundError(
        f"Plugin '{plugin_name}' not found in {search_dirs}"
    )
