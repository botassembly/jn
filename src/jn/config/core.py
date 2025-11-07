"""Core config state management and persistence helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from jn.home import load_json, resolve_config_path, save_json
from jn.models import Config

_CONFIG: Config | None = None
_CONFIG_PATH: Path | None = None


def reset() -> None:
    """Reset cached config (primarily for tests)."""

    global _CONFIG, _CONFIG_PATH
    _CONFIG = None
    _CONFIG_PATH = None


def config_path() -> Path | None:
    """Return the path of the active config, if set."""

    if _CONFIG_PATH is not None:
        return _CONFIG_PATH
    if _CONFIG is not None and _CONFIG.config_path is not None:
        return _CONFIG.config_path
    return None


def _store(config_obj: Config, path: Path) -> Config:
    config_obj.config_path = path
    global _CONFIG, _CONFIG_PATH
    _CONFIG = config_obj
    _CONFIG_PATH = path
    return config_obj


def use(path: Path | str | None = None) -> Config:
    """Load config from ``path`` (or fallback locations) and cache it."""

    target: Optional[Path]
    if path is None:
        target = None
    elif isinstance(path, Path):
        target = path
    else:
        target = Path(path)

    resolved = resolve_config_path(target)
    data = load_json(resolved)
    config_obj = Config.model_validate(data)
    return _store(config_obj, resolved)


def ensure(path: Path | str | None = None) -> Config:
    """Ensure a config is loaded, optionally overriding the path."""

    if path is not None:
        return use(path)
    if _CONFIG is None:
        return use(None)
    return _CONFIG


def require() -> Config:
    """Return the cached config, loading it if necessary."""

    return ensure(None)


def persist(config_obj: Config) -> Config:
    """Persist and cache the given config object."""

    path = config_path()
    if path is None:
        raise RuntimeError("Config path not set; call use() first")

    validated = Config.model_validate(config_obj.model_dump())
    save_json(path, validated.model_dump(exclude_none=True))
    return _store(validated, path)


__all__ = ["config_path", "ensure", "persist", "require", "reset", "use"]
