"""Converter models and engine-specific configurations."""

from __future__ import annotations

from typing import Any, Dict, Literal

from pydantic import BaseModel, Field


class JqConfig(BaseModel):
    """jq converter configuration."""

    expr: str | None = None
    file: str | None = None
    modules: str | None = None
    raw: bool = False
    args: Dict[str, Any] = Field(default_factory=dict)


class JcConfig(BaseModel):
    """jc converter configuration (CLI output to JSON)."""

    parser: str
    opts: list[str] = Field(default_factory=list)
    unbuffer: bool = False


class JiterConfig(BaseModel):
    """jiter converter configuration (partial JSON recovery)."""

    partial_mode: Literal["off", "on", "trailing-strings"] = "off"
    catch_duplicate_keys: bool = False
    tail_kib: int = 256


class DelimitedConfig(BaseModel):
    """Delimited text converter configuration (CSV/TSV)."""

    delimiter: str = ","
    has_header: bool = True
    quotechar: str = '"'
    fields: list[str] | None = None


class Converter(BaseModel):
    """Converter definition (transforms JSON/NDJSON)."""

    name: str
    engine: Literal["jq", "jc", "jiter", "delimited"]
    jq: JqConfig | None = None
    jc: JcConfig | None = None
    jiter: JiterConfig | None = None
    delimited: DelimitedConfig | None = None


__all__ = [
    "Converter",
    "DelimitedConfig",
    "JcConfig",
    "JiterConfig",
    "JqConfig",
]
