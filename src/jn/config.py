"""Config layer: global project configuration management."""

from pathlib import Path
from typing import Optional

from .home import load_json, resolve_config_path
from .models import Project

__all__ = [
    "get_config",
    "reset_config",
    "set_config",
]

_CONFIG: Optional[Project] = None


def get_config(path: Optional[str | Path] = None) -> Project:
    """
    Return cached Project (load+validate on first use).
    If path is given, (re)load from that path and cache it.
    """
    global _CONFIG
    if path is not None:
        resolved = Path(path) if isinstance(path, str) else path
        data = load_json(resolved)
        _CONFIG = Project.model_validate(data)
        return _CONFIG
    if _CONFIG is None:
        p = resolve_config_path()
        data = load_json(p)
        _CONFIG = Project.model_validate(data)
    return _CONFIG


def set_config(project: Project) -> None:
    """Inject a Project (for unit tests)."""
    global _CONFIG
    _CONFIG = project


def reset_config() -> None:
    """Reset cached config (for tests)."""
    global _CONFIG
    _CONFIG = None
