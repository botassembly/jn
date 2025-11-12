"""Pattern matching registry for plugin resolution (logic module)."""

import re
from typing import Dict, List, Optional, Tuple

from ..plugins.discovery import PluginMetadata


class PatternRegistry:
    """Registry that maps file patterns to plugins using regex."""

    def __init__(self):
        # Store (regex, plugin_name, specificity, role)
        self.patterns: List[Tuple[re.Pattern, str, int, Optional[str]]] = []

    def register_plugin(self, plugin: PluginMetadata) -> None:
        for pattern_str in plugin.matches:
            try:
                regex = re.compile(pattern_str)
            except re.error:
                continue
            specificity = len(pattern_str)
            self.patterns.append((regex, plugin.name, specificity, plugin.role))
        self.patterns.sort(key=lambda x: x[2], reverse=True)

    def match(self, source: str) -> Optional[str]:
        for regex, plugin_name, _, _ in self.patterns:
            if regex.search(source):
                return plugin_name
        return None

    def match_role(self, source: str, role: str) -> Optional[str]:
        for regex, plugin_name, _, plugin_role in self.patterns:
            if plugin_role != role:
                continue
            if regex.search(source):
                return plugin_name
        return None

    def plan_for_read(self, source: str, plugins: Dict[str, PluginMetadata]) -> List[str]:
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
