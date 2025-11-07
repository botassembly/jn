"""Converter models and engine-specific configurations.

IMPORTANT: Converters only handle JSON → JSON transformations.
For format boundaries (non-JSON ↔ JSON), use adapters instead.
See spec/arch/adapters.md for adapter documentation.
"""

from __future__ import annotations

from typing import Any, Dict, Literal

from pydantic import BaseModel, Field


class JqConfig(BaseModel):
    """jq converter configuration (JSON → JSON transformation)."""

    expr: str | None = None
    file: str | None = None
    modules: str | None = None
    raw: bool = False
    args: Dict[str, Any] = Field(default_factory=dict)


class Converter(BaseModel):
    """Converter definition (transforms JSON/NDJSON).

    Converters only support JSON → JSON transformations via jq.
    For non-JSON input/output, use source/target adapters instead.
    """

    name: str
    engine: Literal["jq"] = "jq"
    jq: JqConfig | None = None


__all__ = [
    "Converter",
    "JqConfig",
]
