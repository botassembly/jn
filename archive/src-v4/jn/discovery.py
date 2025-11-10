"""Plugin discovery system.

Scans filesystem for JN plugins and extracts metadata without importing Python modules.
Uses regex-based parsing of META headers and PEP 723 dependency blocks.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field


@dataclass
class PluginMetadata:
    """Metadata extracted from a plugin file."""

    name: str
    path: str
    type: Optional[str] = None  # source, filter, target
    handles: List[str] = field(default_factory=list)  # File extensions or URL patterns
    command: Optional[str] = None  # Shell command name
    streaming: bool = False
    dependencies: List[str] = field(default_factory=list)  # PEP 723 dependencies
    mtime: float = 0.0  # File modification time
    category: Optional[str] = None  # readers, writers, filters, shell, http
    description: Optional[str] = None  # Plugin description
    keywords: List[str] = field(default_factory=list)  # Search keywords


def get_plugin_paths() -> List[Path]:
    """Return standard plugin search paths in priority order.

    Priority:
        1. User plugins: ~/.jn/plugins/
        2. Project plugins: ./.jn/plugins/
        3. Package plugins: <package>/plugins/
        4. System plugins: /usr/local/share/jn/plugins/

    Returns:
        List of Path objects to search for plugins
    """
    paths = []

    # User plugins
    user_home = Path.home()
    user_plugins = user_home / '.jn' / 'plugins'
    if user_plugins.exists():
        paths.append(user_plugins)

    # Project plugins
    project_plugins = Path.cwd() / '.jn' / 'plugins'
    if project_plugins.exists():
        paths.append(project_plugins)

    # Package plugins (relative to this file)
    package_root = Path(__file__).parent.parent.parent
    package_plugins = package_root / 'plugins'
    if package_plugins.exists():
        paths.append(package_plugins)

    # System plugins
    system_plugins = Path('/usr/local/share/jn/plugins')
    if system_plugins.exists():
        paths.append(system_plugins)

    return paths


def parse_plugin_metadata(file_path: Path) -> Optional[PluginMetadata]:
    """Extract metadata from plugin file using regex (no imports).

    Parses:
        - META headers: # META: type=source, handles=[".csv"]
        - PEP 723 dependencies: # dependencies = ["package>=1.0"]
        - File modification time

    Args:
        file_path: Path to plugin .py file

    Returns:
        PluginMetadata object or None if not a valid plugin
    """
    if not file_path.suffix == '.py':
        return None

    try:
        content = file_path.read_text(encoding='utf-8')
    except (IOError, UnicodeDecodeError):
        return None

    # Extract plugin name from filename
    name = file_path.stem

    # Determine category from directory structure
    category = None
    if file_path.parent.name in ('readers', 'writers', 'filters', 'shell', 'http'):
        category = file_path.parent.name

    # Parse META header
    # Format: # META: type=source, handles=[".csv", ".tsv"], streaming=true
    meta_pattern = r'#\s*META:\s*(.+)'
    meta_match = re.search(meta_pattern, content)

    plugin_type = None
    handles = []
    command = None
    streaming = False

    if meta_match:
        meta_content = meta_match.group(1)

        # Extract type
        type_match = re.search(r'type=(\w+)', meta_content)
        if type_match:
            plugin_type = type_match.group(1)

        # Extract handles (file extensions or patterns)
        handles_match = re.search(r'handles=\[(.*?)\]', meta_content)
        if handles_match:
            handles_str = handles_match.group(1)
            # Parse quoted strings
            handles = re.findall(r'["\']([^"\']+)["\']', handles_str)

        # Extract command
        command_match = re.search(r'command=["\']([^"\']+)["\']', meta_content)
        if command_match:
            command = command_match.group(1)

        # Extract streaming flag
        streaming_match = re.search(r'streaming=(true|false)', meta_content)
        if streaming_match:
            streaming = streaming_match.group(1) == 'true'

    # Parse PEP 723 dependencies
    # Format: # dependencies = ["package>=1.0", "other"]
    dependencies = []
    dep_pattern = r'#\s*dependencies\s*=\s*\[(.*?)\]'
    dep_match = re.search(dep_pattern, content)
    if dep_match:
        dep_str = dep_match.group(1)
        dependencies = re.findall(r'["\']([^"\']+)["\']', dep_str)

    # Parse KEYWORDS
    # Format: # KEYWORDS: csv, data, parsing
    keywords = []
    keywords_pattern = r'#\s*KEYWORDS:\s*(.+)'
    keywords_match = re.search(keywords_pattern, content)
    if keywords_match:
        keywords_str = keywords_match.group(1).strip()
        keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]

    # Parse DESCRIPTION (from comment or docstring)
    # Format: # DESCRIPTION: Read CSV files...
    description = None
    desc_pattern = r'#\s*DESCRIPTION:\s*(.+)'
    desc_match = re.search(desc_pattern, content)
    if desc_match:
        description = desc_match.group(1).strip()
    else:
        # Try to extract from module docstring (first triple-quoted string)
        docstring_pattern = r'"""(.+?)"""'
        docstring_match = re.search(docstring_pattern, content, re.DOTALL)
        if docstring_match:
            # Get first line of docstring
            docstring = docstring_match.group(1).strip()
            description = docstring.split('\n')[0].strip()

    # Get file modification time
    mtime = file_path.stat().st_mtime

    return PluginMetadata(
        name=name,
        path=str(file_path),
        type=plugin_type,
        handles=handles,
        command=command,
        streaming=streaming,
        dependencies=dependencies,
        mtime=mtime,
        category=category,
        description=description,
        keywords=keywords
    )


def discover_plugins(
    scan_paths: Optional[List[Path]] = None,
    plugin_types: Optional[Set[str]] = None
) -> Dict[str, PluginMetadata]:
    """Discover all plugins in scan paths.

    Recursively scans directories for .py files and extracts metadata.
    Returns a registry mapping plugin names to metadata.

    Args:
        scan_paths: Paths to scan (default: get_plugin_paths())
        plugin_types: Filter by plugin types (default: all types)

    Returns:
        Dict mapping plugin name to PluginMetadata
    """
    if scan_paths is None:
        scan_paths = get_plugin_paths()

    registry = {}

    for search_path in scan_paths:
        if not search_path.exists():
            continue

        # Recursively find all .py files
        for py_file in search_path.rglob('*.py'):
            # Skip __init__.py and test files
            if py_file.name in ('__init__.py', 'conftest.py'):
                continue
            if py_file.name.startswith('test_'):
                continue

            # Parse metadata
            metadata = parse_plugin_metadata(py_file)
            if metadata is None:
                continue

            # Filter by type if specified
            if plugin_types and metadata.type not in plugin_types:
                continue

            # Add to registry (first match wins - priority order)
            if metadata.name not in registry:
                registry[metadata.name] = metadata

    return registry


def get_plugins_by_extension(extension: str) -> List[PluginMetadata]:
    """Find all plugins that handle a given file extension.

    Args:
        extension: File extension (e.g., ".csv", ".json")

    Returns:
        List of PluginMetadata objects that handle the extension
    """
    all_plugins = discover_plugins()
    matching = []

    for plugin in all_plugins.values():
        if extension in plugin.handles:
            matching.append(plugin)

    return matching


def get_plugins_by_command(command: str) -> List[PluginMetadata]:
    """Find all plugins that wrap a given shell command.

    Args:
        command: Shell command name (e.g., "ls", "ps")

    Returns:
        List of PluginMetadata objects for the command
    """
    all_plugins = discover_plugins()
    matching = []

    for plugin in all_plugins.values():
        if plugin.command == command:
            matching.append(plugin)

    return matching


def get_plugins_changed_since(timestamp: float) -> List[PluginMetadata]:
    """Find all plugins modified after a given timestamp.

    Useful for cache invalidation.

    Args:
        timestamp: Unix timestamp

    Returns:
        List of PluginMetadata objects modified after timestamp
    """
    all_plugins = discover_plugins()
    return [p for p in all_plugins.values() if p.mtime > timestamp]
