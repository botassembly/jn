"""Filter models for the simplified registry architecture.

Filters are jq transformations that operate on JSON/NDJSON data.
The term 'filter' follows jq terminology (not 'converter').
"""

from __future__ import annotations

from pydantic import BaseModel


class Filter(BaseModel):
    """Filter definition (jq transformation).

    Filters apply jq queries to transform JSON/NDJSON data.
    Following jq's terminology, we call these 'filters' not 'converters'.

    The query field can contain any valid jq expression.
    """

    name: str
    query: str  # jq expression (required)
    description: str | None = None  # Optional human-readable description


__all__ = ["Filter"]
