"""JN core business logic.

This module contains all business logic separated from CLI presentation:
- pipeline: Data pipeline execution and subprocess management
- plugins: Plugin discovery and introspection
- streaming: NDJSON stream utilities (head, tail, etc.)
"""

from .pipeline import (
    PipelineError,
    convert,
    filter_stream,
    read_source,
    start_reader,
    write_destination,
)
from .plugins import (
    PluginInfo,
    call_plugin,
    find_plugin,
    infer_plugin_type,
    list_plugins,
)
from .streaming import head, tail

__all__ = [
    # Pipeline
    "PipelineError",
    "start_reader",
    "read_source",
    "write_destination",
    "convert",
    "filter_stream",
    # Plugins
    "PluginInfo",
    "list_plugins",
    "find_plugin",
    "call_plugin",
    "infer_plugin_type",
    # Streaming
    "head",
    "tail",
]
