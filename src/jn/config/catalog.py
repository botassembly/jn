"""Read operations over the cached config."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Protocol, Sequence, Tuple, TypeVar

from jn.models import Config, Converter, Pipeline, Source, Target

from .core import ensure
from .types import CollectionName

__all__ = [
    "converter_names",
    "fetch_item",
    "get_converter",
    "get_item",
    "get_names",
    "get_pipeline",
    "get_source",
    "get_target",
    "has_converter",
    "has_item",
    "has_pipeline",
    "has_source",
    "has_target",
    "list_items",
    "pipeline_names",
    "source_names",
    "target_names",
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


def source_names(path: Optional[Path | str] = None) -> Tuple[str, ...]:
    return get_names("sources", path)


def target_names(path: Optional[Path | str] = None) -> Tuple[str, ...]:
    return get_names("targets", path)


def converter_names(path: Optional[Path | str] = None) -> Tuple[str, ...]:
    return get_names("converters", path)


def pipeline_names(path: Optional[Path | str] = None) -> Tuple[str, ...]:
    return get_names("pipelines", path)


def has_item(
    name: str,
    kind: CollectionName,
    path: Optional[Path | str] = None,
) -> bool:
    return name in get_names(kind, path)


def has_source(name: str, path: Optional[Path | str] = None) -> bool:
    return has_item(name, "sources", path)


def has_target(name: str, path: Optional[Path | str] = None) -> bool:
    return has_item(name, "targets", path)


def has_converter(name: str, path: Optional[Path | str] = None) -> bool:
    return has_item(name, "converters", path)


def has_pipeline(name: str, path: Optional[Path | str] = None) -> bool:
    return has_item(name, "pipelines", path)


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


def get_source(
    name: str, path: Optional[Path | str] = None
) -> Optional[Source]:
    return _get_by_name(name, "sources", path)


def get_target(
    name: str, path: Optional[Path | str] = None
) -> Optional[Target]:
    return _get_by_name(name, "targets", path)


def get_converter(
    name: str, path: Optional[Path | str] = None
) -> Optional[Converter]:
    return _get_by_name(name, "converters", path)


def get_pipeline(
    name: str, path: Optional[Path | str] = None
) -> Optional[Pipeline]:
    return _get_by_name(name, "pipelines", path)


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
