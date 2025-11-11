"""Backwards-compatible re-export of plugin service functions.

This module now delegates to jn.plugins.service to keep import stability.
"""

from ..plugins.service import (  # noqa: F401
    PluginInfo,
    call_plugin,
    detect_plugin_methods,
    extract_description,
    extract_method_docstring,
    find_plugin,
    get_plugin_info,
    infer_plugin_type,
    list_plugins,
)
