"""JN (Junction): Source → jq → Target streaming pipelines."""

from . import config
from .options import ConfigPath, ConfigPathType

__all__ = ["__version__", "ConfigPath", "ConfigPathType", "config"]

__version__ = "0.0.1"
