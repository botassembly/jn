"""Pipeline definitions."""

from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


class Step(BaseModel):
    """Pipeline step reference."""

    type: Literal["source", "converter", "target"]
    ref: str
    args: Dict[str, Any] = Field(default_factory=dict)


class Pipeline(BaseModel):
    """Pipeline definition (source → converters → target)."""

    name: str
    steps: List[Step]


__all__ = ["Pipeline", "Step"]
