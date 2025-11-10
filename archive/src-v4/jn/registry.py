"""Extension and pattern registry for plugin auto-selection.

Maps file extensions, URL patterns, and commands to appropriate plugins.
Provides caching and user customization support.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from .discovery import discover_plugins, PluginMetadata


@dataclass
class RegistryEntry:
    """Entry in the plugin registry."""

    pattern: str  # File extension, URL pattern, or command
    plugin_name: str
    priority: int = 0  # Higher priority wins
    source: str = "default"  # default, user, auto


class PluginRegistry:
    """Registry mapping patterns to plugins.

    Provides:
        - Extension to plugin mapping (.csv → csv_reader)
        - URL pattern to plugin mapping (https:// → http_get)
        - Command to plugin mapping (ls → ls)
        - User overrides and customization
        - Persistent storage in ~/.jn/registry.json
    """

    def __init__(self, registry_path: Optional[Path] = None):
        """Initialize registry.

        Args:
            registry_path: Path to registry file (default: ~/.jn/registry.json)
        """
        if registry_path is None:
            registry_path = Path.home() / '.jn' / 'registry.json'

        self.registry_path = registry_path
        self.entries: List[RegistryEntry] = []
        self._plugin_cache: Optional[Dict[str, PluginMetadata]] = None

        # Load from file or initialize with defaults
        if registry_path.exists():
            self.load()
        else:
            self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Initialize with default mappings from bundled plugins."""
        # Discover all plugins
        plugins = discover_plugins()

        # Build default mappings from plugin metadata
        for plugin in plugins.values():
            # Add file extension mappings
            for extension in plugin.handles:
                if extension.startswith('.'):
                    # Map extension to reader or writer based on category
                    if plugin.category == 'readers':
                        self.add_entry(extension, plugin.name, source='default')
                    elif plugin.category == 'writers':
                        # Writers are mapped with a special prefix
                        self.add_entry(f'write{extension}', plugin.name, source='default')

            # Add command mappings
            if plugin.command:
                self.add_entry(f'cmd:{plugin.command}', plugin.name, source='default')

        # Add URL pattern mappings (will be used when http plugins exist)
        url_patterns = [
            ('http://', 'http_get'),
            ('https://', 'http_get'),
            ('ftp://', 'ftp_get'),
            ('ftps://', 'ftp_get'),
            ('s3://', 's3_get'),
        ]
        for pattern, plugin in url_patterns:
            self.add_entry(pattern, plugin, source='default')

    def add_entry(
        self,
        pattern: str,
        plugin_name: str,
        priority: int = 0,
        source: str = "default"
    ) -> None:
        """Add or update a registry entry.

        Args:
            pattern: Pattern to match (extension, URL prefix, command)
            plugin_name: Name of plugin to use
            priority: Priority (higher wins)
            source: Source of entry (default, user, auto)
        """
        # Remove existing entry with same pattern and source
        self.entries = [
            e for e in self.entries
            if not (e.pattern == pattern and e.source == source)
        ]

        # Add new entry
        self.entries.append(RegistryEntry(
            pattern=pattern,
            plugin_name=plugin_name,
            priority=priority,
            source=source
        ))

    def get_plugin_for_extension(self, extension: str) -> Optional[str]:
        """Get plugin name for file extension.

        Args:
            extension: File extension (e.g., ".csv", ".json")

        Returns:
            Plugin name or None if no match
        """
        if not extension.startswith('.'):
            extension = f'.{extension}'

        # Find matching entries, sorted by priority
        matches = [
            e for e in self.entries
            if e.pattern == extension
        ]
        matches.sort(key=lambda e: e.priority, reverse=True)

        return matches[0].plugin_name if matches else None

    def get_plugin_for_url(self, url: str) -> Optional[str]:
        """Get plugin name for URL pattern.

        Args:
            url: URL string

        Returns:
            Plugin name or None if no match
        """
        # Find matching URL patterns
        matches = []
        for entry in self.entries:
            if url.startswith(entry.pattern):
                matches.append(entry)

        # Sort by pattern length (longer = more specific) then priority
        matches.sort(key=lambda e: (len(e.pattern), e.priority), reverse=True)

        return matches[0].plugin_name if matches else None

    def get_plugin_for_command(self, command: str) -> Optional[str]:
        """Get plugin name for shell command.

        Args:
            command: Command name (e.g., "ls", "ps")

        Returns:
            Plugin name or None if no match
        """
        pattern = f'cmd:{command}'
        matches = [
            e for e in self.entries
            if e.pattern == pattern
        ]
        matches.sort(key=lambda e: e.priority, reverse=True)

        return matches[0].plugin_name if matches else None

    def save(self) -> None:
        """Save registry to disk."""
        # Ensure directory exists
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert entries to dict
        data = {
            'entries': [
                {
                    'pattern': e.pattern,
                    'plugin_name': e.plugin_name,
                    'priority': e.priority,
                    'source': e.source
                }
                for e in self.entries
            ]
        }

        # Write to file
        with open(self.registry_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        """Load registry from disk."""
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.entries = [
                RegistryEntry(**entry)
                for entry in data.get('entries', [])
            ]
        except (IOError, json.JSONDecodeError):
            # If load fails, initialize with defaults
            self._initialize_defaults()

    def list_patterns(self, source: Optional[str] = None) -> List[RegistryEntry]:
        """List all registry entries.

        Args:
            source: Filter by source (default, user, auto)

        Returns:
            List of RegistryEntry objects
        """
        if source is None:
            return self.entries.copy()
        return [e for e in self.entries if e.source == source]

    def remove_pattern(self, pattern: str, source: Optional[str] = None) -> bool:
        """Remove a pattern from registry.

        Args:
            pattern: Pattern to remove
            source: Only remove if from this source (optional)

        Returns:
            True if entry was removed
        """
        original_len = len(self.entries)

        if source is None:
            self.entries = [e for e in self.entries if e.pattern != pattern]
        else:
            self.entries = [
                e for e in self.entries
                if not (e.pattern == pattern and e.source == source)
            ]

        return len(self.entries) < original_len

    def rebuild_from_plugins(self) -> None:
        """Rebuild default entries from discovered plugins.

        Preserves user entries, updates default entries.
        """
        # Save user entries
        user_entries = [e for e in self.entries if e.source == 'user']

        # Clear and rebuild defaults
        self.entries = []
        self._initialize_defaults()

        # Restore user entries (will override defaults due to priority)
        for entry in user_entries:
            entry.priority = 100  # User entries always win
            self.entries.append(entry)


# Global registry instance
_global_registry: Optional[PluginRegistry] = None


def get_registry() -> PluginRegistry:
    """Get the global plugin registry instance.

    Lazy initialization on first access.

    Returns:
        Global PluginRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = PluginRegistry()
    return _global_registry


def resolve_plugin(source: str) -> Optional[str]:
    """Resolve source to appropriate plugin name.

    Checks in order:
        1. URL patterns (http://, https://, s3://, etc.)
        2. File extensions (if source is a file path)
        3. Shell commands (if source is a command name)

    Args:
        source: Source string (URL, file path, or command)

    Returns:
        Plugin name or None if no match
    """
    registry = get_registry()

    # Check URL patterns
    if '://' in source:
        plugin = registry.get_plugin_for_url(source)
        if plugin:
            return plugin

    # Check file extension
    if '.' in source:
        extension = Path(source).suffix
        if extension:
            plugin = registry.get_plugin_for_extension(extension)
            if plugin:
                return plugin

    # Check command
    # Assume it's a command if it's a simple word
    if re.match(r'^\w+$', source):
        plugin = registry.get_plugin_for_command(source)
        if plugin:
            return plugin

    return None
