"""Backwards-compatible re-export of plugin discovery APIs.

The discovery logic now lives in jn.plugins.discovery.
"""

from .plugins.discovery import (  # noqa: F401
    PEP723_PATTERN,
    PluginMetadata,
    discover_plugins,
    get_cached_plugins,
    get_cached_plugins_with_fallback,
    get_plugin_by_name,
    load_cache,
    parse_pep723,
    save_cache,
)
