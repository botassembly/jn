"""Pattern matching registry for plugin resolution."""

import re
from typing import List, Optional, Tuple

from .discovery import PluginMetadata


class PatternRegistry:
    """Registry that maps file patterns to plugins using regex."""

    def __init__(self):
        """Initialize empty registry."""
        self.patterns: List[Tuple[re.Pattern, str, int]] = (
            []
        )  # (regex, plugin_name, specificity)

    def register_plugin(self, plugin: PluginMetadata) -> None:
        """Register a plugin's patterns.

        Args:
            plugin: Plugin metadata with matches list
        """
        for pattern_str in plugin.matches:
            # Compile regex pattern
            try:
                regex = re.compile(pattern_str)
            except re.error:
                continue  # Skip invalid patterns

            # Calculate specificity (longer pattern = more specific)
            specificity = len(pattern_str)

            self.patterns.append((regex, plugin.name, specificity))

        # Sort by specificity (highest first)
        self.patterns.sort(key=lambda x: x[2], reverse=True)

    def match(self, source: str) -> Optional[str]:
        """Find best matching plugin for source.

        Tries patterns in specificity order (most specific first).

        Args:
            source: Source string (filename, URL, etc.)

        Returns:
            Plugin name or None if no match
        """
        for regex, plugin_name, _ in self.patterns:
            if regex.search(source):
                return plugin_name

        return None


def build_registry(plugins: dict) -> PatternRegistry:
    """Build pattern registry from discovered plugins.

    Args:
        plugins: Dict of plugin name → PluginMetadata

    Returns:
        PatternRegistry ready for matching
    """
    registry = PatternRegistry()

    for plugin in plugins.values():
        registry.register_plugin(plugin)

    return registry
