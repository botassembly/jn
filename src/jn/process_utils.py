"""Process and subprocess utilities shared across JN layers.

Includes safe wrappers around subprocess as well as helper utilities for
propagating coverage configuration into child processes. Lives outside the
CLI package so that service layers (e.g., plugins) can depend on it without
creating an upward dependency on jn.cli.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

CommandArg = str | os.PathLike[str]


def _normalize_command(cmd: Sequence[CommandArg]) -> list[str]:
    """Validate and normalize subprocess command arguments."""
    if not cmd:
        msg = "Command must include at least one argument"
        raise ValueError(msg)

    normalized: list[str] = []
    for arg in cmd:
        if isinstance(arg, os.PathLike):
            value = os.fspath(arg)
        elif isinstance(arg, str):
            value = arg
        else:
            msg = "Command arguments must be strings or os.PathLike"
            raise TypeError(msg)

        if not value.strip():
            msg = "Command arguments cannot be empty or whitespace"
            raise ValueError(msg)

        normalized.append(value)

    return normalized


def popen_with_validation(
    cmd: Sequence[CommandArg], **kwargs: Any
) -> subprocess.Popen[Any]:
    """Run subprocess.Popen with validation to satisfy security lint checks."""
    normalized_cmd = _normalize_command(cmd)
    return subprocess.Popen(normalized_cmd, **kwargs)  # noqa: S603


def run_with_validation(
    cmd: Sequence[CommandArg], **kwargs: Any
) -> subprocess.CompletedProcess[Any]:
    """Run subprocess.run with validation to satisfy security lint checks."""
    normalized_cmd = _normalize_command(cmd)
    return subprocess.run(normalized_cmd, **kwargs)  # noqa: S603


def _repo_root() -> Path:
    """Locate repository root by searching for sitecustomize.py above this file."""
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "sitecustomize.py").exists():
            return parent
    # Fallback to current working directory
    return Path.cwd()


def build_subprocess_env_for_coverage() -> dict:
    """Return an env dict that enables coverage in subprocesses.

    - If COVERAGE_PROCESS_START is set, ensure sitecustomize.py is importable by
      prepending the repo root to PYTHONPATH.
    - Force coverage data files to land in repo root so combine finds them.
    - Also includes JN environment variables (JN_HOME, JN_WORKING_DIR, etc.)
    """
    # Start with JN environment variables
    from .context import get_plugin_env

    env = get_plugin_env()

    # Add coverage configuration if needed
    if env.get("COVERAGE_PROCESS_START"):
        root = _repo_root()
        py_path = env.get("PYTHONPATH", "")
        root_str = str(root)
        if py_path:
            if root_str not in py_path.split(os.pathsep):
                env["PYTHONPATH"] = root_str + os.pathsep + py_path
        else:
            env["PYTHONPATH"] = root_str

        # Centralize coverage data output
        env.setdefault("COVERAGE_RCFILE", str(root / ".coveragerc"))
        env.setdefault("COVERAGE_FILE", str(root / ".coverage"))

    return env
