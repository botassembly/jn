"""Core config state management and persistence helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from jn.home import load_json, resolve_config_path, save_json
from jn.models import Config


class ConfigCache:
    """Thread-safe config cache with dependency injection support."""

    def __init__(self) -> None:
        """Initialize empty config cache."""
        self._config: Config | None = None
        self._config_path: Path | None = None

    def reset(self) -> None:
        """Reset cached config (primarily for tests)."""
        self._config = None
        self._config_path = None

    def config_path(self) -> Path | None:
        """Return the path of the active config, if set."""
        if self._config_path is not None:
            return self._config_path
        if self._config is not None and self._config.config_path is not None:
            return self._config.config_path
        return None

    def _store(self, config_obj: Config, path: Path) -> Config:
        """Store config and path in cache."""
        config_obj.config_path = path
        self._config = config_obj
        self._config_path = path
        return config_obj

    def use(self, path: Path | str | None = None) -> Config:
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
        return self._store(config_obj, resolved)

    def ensure(self, path: Path | str | None = None) -> Config:
        """Ensure a config is loaded, optionally overriding the path."""
        if path is not None:
            return self.use(path)
        if self._config is None:
            return self.use(None)
        return self._config

    def require(self) -> Config:
        """Return the cached config, loading it if necessary."""
        return self.ensure(None)

    def persist(self, config_obj: Config) -> Config:
        """Persist and cache the given config object."""
        path = self.config_path()
        if path is None:
            raise RuntimeError("Config path not set; call use() first")

        validated = Config.model_validate(config_obj.model_dump())
        save_json(path, validated.model_dump(exclude_none=True))
        return self._store(validated, path)


# Global instance for backward compatibility
_cache = ConfigCache()


# Public API functions delegate to the global cache instance
def reset() -> None:
    """Reset cached config (primarily for tests)."""
    _cache.reset()


def config_path() -> Path | None:
    """Return the path of the active config, if set."""
    return _cache.config_path()


def use(path: Path | str | None = None) -> Config:
    """Load config from ``path`` (or fallback locations) and cache it."""
    return _cache.use(path)


def ensure(path: Path | str | None = None) -> Config:
    """Ensure a config is loaded, optionally overriding the path."""
    return _cache.ensure(path)


def require() -> Config:
    """Return the cached config, loading it if necessary."""
    return _cache.require()


def persist(config_obj: Config) -> Config:
    """Persist and cache the given config object."""
    return _cache.persist(config_obj)


__all__ = [
    "ConfigCache",
    "config_path",
    "ensure",
    "persist",
    "require",
    "reset",
    "use",
]
