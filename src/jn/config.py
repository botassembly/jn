"""Config layer: global configuration management."""

from pathlib import Path
from typing import Dict, List, Optional

from .home import load_json, resolve_config_path
from .models import Converter, Pipeline, Project, Source, Target

__all__ = [
    "get_config",
    "get_converter",
    "get_pipeline",
    "get_source",
    "get_target",
    "has_converter",
    "has_pipeline",
    "has_source",
    "has_target",
    "parse_key_value_pairs",
    "reset_config",
    "set_config",
]

_CONFIG: Optional[Project] = None


def parse_key_value_pairs(items: List[str]) -> Dict[str, str]:
    """
    Parse key=value pairs from CLI flags.

    Args:
        items: List of "key=value" strings

    Returns:
        Dictionary of parsed key-value pairs

    Raises:
        ValueError: If any item doesn't contain '='
    """
    result = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid format: {item} (expected key=value)")
        key, value = item.split("=", 1)
        result[key] = value
    return result


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
        _CONFIG.config_path = resolved
        return _CONFIG
    if _CONFIG is None:
        p = resolve_config_path()
        data = load_json(p)
        _CONFIG = Project.model_validate(data)
        _CONFIG.config_path = p
    return _CONFIG


def set_config(project: Project) -> None:
    """Inject a Project (for unit tests)."""
    global _CONFIG
    _CONFIG = project


def reset_config() -> None:
    """Reset cached config (for tests)."""
    global _CONFIG
    _CONFIG = None


def get_source(name: str, path: Optional[str | Path] = None) -> Optional[Source]:
    """Get source by name, or None if not found."""
    config = get_config(path)
    return next((s for s in config.sources if s.name == name), None)


def get_target(name: str, path: Optional[str | Path] = None) -> Optional[Target]:
    """Get target by name, or None if not found."""
    config = get_config(path)
    return next((t for t in config.targets if t.name == name), None)


def get_converter(name: str, path: Optional[str | Path] = None) -> Optional[Converter]:
    """Get converter by name, or None if not found."""
    config = get_config(path)
    return next((c for c in config.converters if c.name == name), None)


def get_pipeline(name: str, path: Optional[str | Path] = None) -> Optional[Pipeline]:
    """Get pipeline by name, or None if not found."""
    config = get_config(path)
    return next((p for p in config.pipelines if p.name == name), None)


def has_source(name: str, path: Optional[str | Path] = None) -> bool:
    """Check if source exists."""
    config = get_config(path)
    return any(s.name == name for s in config.sources)


def has_target(name: str, path: Optional[str | Path] = None) -> bool:
    """Check if target exists."""
    config = get_config(path)
    return any(t.name == name for t in config.targets)


def has_converter(name: str, path: Optional[str | Path] = None) -> bool:
    """Check if converter exists."""
    config = get_config(path)
    return any(c.name == name for c in config.converters)


def has_pipeline(name: str, path: Optional[str | Path] = None) -> bool:
    """Check if pipeline exists."""
    config = get_config(path)
    return any(p.name == name for p in config.pipelines)
