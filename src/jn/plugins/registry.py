"""Pattern matching registry for plugin resolution (logic module)."""

import re
from typing import List, Optional, Tuple

from ..plugins.discovery import PluginMetadata


class PatternRegistry:
    """Registry that maps file patterns to plugins using regex."""

    def __init__(self):
        self.patterns: List[Tuple[re.Pattern, str, int]] = []

    def register_plugin(self, plugin: PluginMetadata) -> None:
        for pattern_str in plugin.matches:
            try:
                regex = re.compile(pattern_str)
            except re.error:
                continue
            specificity = len(pattern_str)
            self.patterns.append((regex, plugin.name, specificity))
        self.patterns.sort(key=lambda x: x[2], reverse=True)

    def match(self, source: str) -> Optional[str]:
        for regex, plugin_name, _ in self.patterns:
            if regex.search(source):
                return plugin_name
        return None


def build_registry(plugins: dict) -> PatternRegistry:
    registry = PatternRegistry()
    for plugin in plugins.values():
        registry.register_plugin(plugin)
    return registry
