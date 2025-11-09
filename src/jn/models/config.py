"""Root configuration model for jn.json.

Simplified registry architecture with just two concepts:
- apis: Generic API configurations (can be source or target)
- filters: jq transformations (renamed from converters)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List

from pydantic import BaseModel, Field, field_validator

from .api import Api
from .filter import Filter


class Config(BaseModel):
    """Root jn.json configuration.

    Simplified registry with just two sections:
    - apis: REST APIs, GraphQL, databases, cloud storage, etc.
    - filters: jq transformations

    Auto-detection handles simple cases:
    - File formats (CSV, JSON, etc.) - detected by extension
    - Shell commands - via jc
    - Plain URLs - no registry needed
    """

    version: str
    name: str
    apis: List[Api] = Field(default_factory=list)
    filters: List[Filter] = Field(default_factory=list)
    config_path: Path | None = Field(default=None, exclude=True)

    @field_validator("apis", "filters")
    @classmethod
    def names_unique(cls, v: List[Any]) -> List[Any]:
        """Ensure names are unique within each collection."""

        names = [x.name for x in v]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate names are not allowed")
        return v

    def get_api(self, name: str) -> Api | None:
        """Get API by name, or None if not found."""

        return next((a for a in self.apis if a.name == name), None)

    def get_filter(self, name: str) -> Filter | None:
        """Get filter by name, or None if not found."""

        return next((f for f in self.filters if f.name == name), None)

    def has_api(self, name: str) -> bool:
        """Check if API exists."""

        return any(a.name == name for a in self.apis)

    def has_filter(self, name: str) -> bool:
        """Check if filter exists."""

        return any(f.name == name for f in self.filters)

    def find_api_by_url(self, url: str) -> Api | None:
        """Find API by longest prefix match on URL.

        Returns the API with the longest matching base_url prefix.
        Example: If registry has both 'https://api.github.com' and
        'https://api.github.com/v4/graphql', and url is
        'https://api.github.com/v4/graphql/query', it returns the latter.
        """

        matches = []
        for api in self.apis:
            if api.base_url and url.startswith(api.base_url):
                matches.append((len(api.base_url), api))

        if not matches:
            return None

        # Return API with longest prefix match
        matches.sort(key=lambda x: x[0], reverse=True)
        return matches[0][1]


__all__ = ["Config"]
