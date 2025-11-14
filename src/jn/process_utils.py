"""Safe wrappers around subprocess helpers used throughout the CLI."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
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
