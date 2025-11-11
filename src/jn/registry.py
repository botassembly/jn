"""Backwards-compatible re-export of registry from jn.plugins.registry."""

from .plugins.registry import (  # noqa: F401
    PatternRegistry,
    build_registry,
)
