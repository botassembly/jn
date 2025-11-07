"""Root configuration model for jn.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List

from pydantic import BaseModel, Field, field_validator

from .converter import Converter
from .pipeline import Pipeline
from .source import Source
from .target import Target


class Config(BaseModel):
    """Root jn.json configuration."""

    version: str
    name: str
    sources: List[Source] = Field(default_factory=list)
    targets: List[Target] = Field(default_factory=list)
    converters: List[Converter] = Field(default_factory=list)
    pipelines: List[Pipeline] = Field(default_factory=list)
    config_path: Path | None = Field(default=None, exclude=True)

    @field_validator("sources", "targets", "converters", "pipelines")
    @classmethod
    def names_unique(cls, v: List[Any]) -> List[Any]:
        """Ensure names are unique within each collection."""

        names = [x.name for x in v]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate names are not allowed")
        return v

    def get_source(self, name: str) -> Source | None:
        """Get source by name, or None if not found."""

        return next((s for s in self.sources if s.name == name), None)

    def get_target(self, name: str) -> Target | None:
        """Get target by name, or None if not found."""

        return next((t for t in self.targets if t.name == name), None)

    def get_converter(self, name: str) -> Converter | None:
        """Get converter by name, or None if not found."""

        return next((c for c in self.converters if c.name == name), None)

    def get_pipeline(self, name: str) -> Pipeline | None:
        """Get pipeline by name, or None if not found."""

        return next((p for p in self.pipelines if p.name == name), None)

    def has_source(self, name: str) -> bool:
        """Check if source exists."""

        return any(s.name == name for s in self.sources)

    def has_target(self, name: str) -> bool:
        """Check if target exists."""

        return any(t.name == name for t in self.targets)

    def has_converter(self, name: str) -> bool:
        """Check if converter exists."""

        return any(c.name == name for c in self.converters)

    def has_pipeline(self, name: str) -> bool:
        """Check if pipeline exists."""

        return any(p.name == name for p in self.pipelines)


__all__ = ["Config"]
