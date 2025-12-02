"""Pattern matching registry for plugin resolution (logic module)."""

import re
from typing import Dict, List, Optional, Tuple

from ..plugins.discovery import PluginMetadata


class PatternRegistry:
    """Registry that maps file patterns to plugins using regex."""

    def __init__(self):
        # Store (regex, plugin_name, specificity, role, is_binary)
        self.patterns: List[Tuple[re.Pattern, str, int, Optional[str], bool]] = []

    def register_plugin(self, plugin: PluginMetadata) -> None:
        # Binary plugins (Zig, Rust) get priority over Python plugins
        is_binary = not plugin.path.endswith(".py")
        for pattern_str in plugin.matches:
            try:
                regex = re.compile(pattern_str)
            except re.error:
                continue
            specificity = len(pattern_str)
            self.patterns.append(
                (regex, plugin.name, specificity, plugin.role, is_binary)
            )
        # Sort by: specificity (descending), then is_binary (True before False)
        self.patterns.sort(key=lambda x: (x[2], x[4]), reverse=True)

    def match(self, source: str) -> Optional[str]:
        for regex, plugin_name, _, _, _ in self.patterns:
            if regex.search(source):
                return plugin_name
        return None

    def match_with_mode(
        self, source: str, mode: str, plugins: Dict[str, PluginMetadata]
    ) -> Optional[str]:
        """Match source to plugin that supports the given mode.

        Args:
            source: Source path/URL to match
            mode: Mode to check ("read" or "write")
            plugins: Dictionary of plugin metadata

        Returns:
            Plugin name if found, None otherwise
        """
        for regex, plugin_name, _, _, _ in self.patterns:
            if regex.search(source):
                plugin = plugins.get(plugin_name)
                if plugin:
                    # If modes is None, plugin supports all modes (Python plugins)
                    if plugin.modes is None or mode in plugin.modes:
                        return plugin_name
        return None

    def match_role(self, source: str, role: str) -> Optional[str]:
        for regex, plugin_name, _, plugin_role, _ in self.patterns:
            if plugin_role != role:
                continue
            if regex.search(source):
                return plugin_name
        return None

    def plan_for_read(
        self, source: str, plugins: Dict[str, PluginMetadata]
    ) -> List[str]:
        """Return an ordered list of plugin names to read a source.

        Strategy:
        - If a protocol plugin matches the full source AND a format plugin matches,
          and the protocol supports raw streaming, return [protocol, format].
        - Else, return the single best match across all patterns (protocol or format).
        """
        # Try to find protocol and format matches independently
        proto = self.match_role(source, "protocol")
        fmt = self.match_role(source, "format")

        if proto and fmt:
            proto_meta = plugins.get(proto)
            if proto_meta and getattr(proto_meta, "supports_raw", False):
                return [proto, fmt]

        # Fallback to a single best match (regardless of role)
        single = self.match(source)
        return [single] if single else []


def build_registry(plugins: dict) -> PatternRegistry:
    registry = PatternRegistry()
    for plugin in plugins.values():
        registry.register_plugin(plugin)
    return registry
