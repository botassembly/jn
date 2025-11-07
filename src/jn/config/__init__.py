"""Config layer facade: state, catalog, mutations, and pipeline helpers."""

from jn.models import Config, Error

from .catalog import (
    converter_names,
    fetch_item,
    get_converter,
    get_item,
    get_names,
    get_pipeline,
    get_source,
    get_target,
    has_converter,
    has_item,
    has_pipeline,
    has_source,
    has_target,
    list_items,
    pipeline_names,
    source_names,
    target_names,
)
from .core import config_path, ensure, require, reset, use
from .mutate import add_converter, add_pipeline, add_source, add_target
from .pipeline import explain_pipeline, run_pipeline
from .types import CollectionName
from .utils import parse_key_value_pairs

set_config_path = use

__all__ = [
    "CollectionName",
    "Config",
    "Error",
    "add_converter",
    "add_pipeline",
    "add_source",
    "add_target",
    "config_path",
    "converter_names",
    "ensure",
    "explain_pipeline",
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
    "parse_key_value_pairs",
    "pipeline_names",
    "require",
    "reset",
    "run_pipeline",
    "set_config_path",
    "source_names",
    "target_names",
]
