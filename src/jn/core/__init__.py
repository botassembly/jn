"""JN core business logic.

This module contains all business logic separated from CLI presentation:
- pipeline: Pipeline error types (deprecated, functions removed)
- plugins: Plugin discovery and introspection
- streaming: NDJSON stream utilities (head, tail, etc.)

Note: Pipeline functions (read_source, write_destination, convert, filter_stream) have
been removed in favor of the addressability system. CLI commands now use AddressResolver
directly for cleaner architecture.
"""

from .pipeline import PipelineError
from .plugins import (
    PluginInfo,
    call_plugin,
    find_plugin,
    infer_plugin_type,
    list_plugins,
)
from .streaming import head, tail

__all__ = [
    "PipelineError",
    "PluginInfo",
    "call_plugin",
    "find_plugin",
    "head",
    "infer_plugin_type",
    "list_plugins",
    "tail",
]
