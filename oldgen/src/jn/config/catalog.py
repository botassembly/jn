"""Read operations over the cached config.

Simplified registry queries for apis and filters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Protocol, Sequence, Tuple, TypeVar

from jn.models import Api, Config, Filter

from .core import ensure
from .types import CollectionName

__all__ = [
    "api_names",
    "fetch_item",
    "filter_names",
    "get_api",
    "get_filter",
    "get_item",
    "get_names",
    "has_api",
    "has_filter",
    "has_item",
    "list_items",
]


class _HasName(Protocol):
    name: str


_Item = TypeVar("_Item", bound=_HasName)


def _collection(config_obj: Config, kind: CollectionName) -> Sequence[_Item]:
    return getattr(config_obj, kind)


def _ordered_names(items: Iterable[_HasName]) -> Tuple[str, ...]:
    return tuple(sorted(item.name for item in items))


def get_names(
    kind: CollectionName,
    path: Optional[Path | str] = None,
) -> Tuple[str, ...]:
    """Return an ordered tuple of names for a collection."""

    config_obj = ensure(path)
    return _ordered_names(_collection(config_obj, kind))


def api_names(path: Optional[Path | str] = None) -> Tuple[str, ...]:
    """Get all API names in sorted order."""
    return get_names("apis", path)


def filter_names(path: Optional[Path | str] = None) -> Tuple[str, ...]:
    """Get all filter names in sorted order."""
    return get_names("filters", path)


def has_item(
    name: str,
    kind: CollectionName,
    path: Optional[Path | str] = None,
) -> bool:
    return name in get_names(kind, path)


def has_api(name: str, path: Optional[Path | str] = None) -> bool:
    """Check if API exists in registry."""
    return has_item(name, "apis", path)


def has_filter(name: str, path: Optional[Path | str] = None) -> bool:
    """Check if filter exists in registry."""
    return has_item(name, "filters", path)


def _get_by_name(
    name: str,
    kind: CollectionName,
    path: Optional[Path | str] = None,
) -> Optional[_Item]:
    config_obj = ensure(path)
    return next(
        (item for item in _collection(config_obj, kind) if item.name == name),
        None,
    )


def get_item(
    name: str,
    kind: CollectionName,
    path: Optional[Path | str] = None,
):
    """Get an item by name from the requested collection."""

    return _get_by_name(name, kind, path)


def get_api(name: str, path: Optional[Path | str] = None) -> Optional[Api]:
    """Get API by name, or None if not found."""
    return _get_by_name(name, "apis", path)


def get_filter(
    name: str, path: Optional[Path | str] = None
) -> Optional[Filter]:
    """Get filter by name, or None if not found."""
    return _get_by_name(name, "filters", path)


def list_items(
    kind: CollectionName,
    path: Optional[Path | str] = None,
) -> Tuple[str, ...]:
    """Compatibility helper used by the CLI layer."""

    return get_names(kind, path)


def fetch_item(
    kind: CollectionName,
    name: str,
    path: Optional[Path | str] = None,
):
    """Compatibility helper used by the CLI layer."""

    return get_item(name, kind, path)
