"""Config layer facade: state, catalog, and mutations.

Simplified for apis and filters architecture.
"""

from jn.models import Config, Error

from .catalog import (
    api_names,
    fetch_item,
    filter_names,
    get_api,
    get_filter,
    get_item,
    get_names,
    has_api,
    has_filter,
    has_item,
    list_items,
)
from .core import config_path, ensure, persist, require, reset, use
from .mutate import add_api, add_filter
from .types import CollectionName
from .utils import parse_key_value_pairs, substitute_template

set_config_path = use

__all__ = [
    "CollectionName",
    "Config",
    "Error",
    "add_api",
    "add_filter",
    "api_names",
    "config_path",
    "ensure",
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
    "parse_key_value_pairs",
    "persist",
    "require",
    "reset",
    "set_config_path",
    "substitute_template",
]
