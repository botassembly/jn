"""Plan models for explain outputs."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel


class PipelinePlan(BaseModel):
    """Result of explaining a pipeline (resolved plan without execution)."""

    pipeline: str
    steps: List[Dict[str, Any]]


__all__ = ["PipelinePlan"]
