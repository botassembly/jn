"""JN (Junction): Source → jq → Target streaming pipelines."""

from . import config
from .options import ConfigPath, ConfigPathType

__all__ = ["ConfigPath", "ConfigPathType", "__version__", "config"]

__version__ = "0.0.1"
