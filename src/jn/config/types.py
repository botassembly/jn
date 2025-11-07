"""Shared typing definitions for the config package."""

from typing import Literal

CollectionName = Literal["sources", "targets", "converters", "pipelines"]

__all__ = ["CollectionName"]
