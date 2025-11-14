"""JN CLI layer.

Expose ``cli`` and ``main`` lazily to avoid importing ``jn.cli.main``
at package import time. This prevents the RuntimeWarning emitted when
executing ``python -m jn.cli.main`` (runpy warns if the submodule is
already in ``sys.modules`` due to eager re-exports in ``__init__``).
"""

__all__ = ["cli", "main", "plugin"]


def __getattr__(name):  # pragma: no cover - trivial lazy import
    if name in {"cli", "main"}:
        from .main import cli as _cli
        from .main import main as _main

        return _cli if name == "cli" else _main
    if name == "plugin":
        from .plugins import plugin as _plugin

        return _plugin
    raise AttributeError(name)
