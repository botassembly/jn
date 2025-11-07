"""Shared CLI helpers for outside-in integration tests."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Mapping

from jn.cli import app


def init_config(runner, path) -> None:
    result = runner.invoke(app, ["init", "--jn", str(path), "--force"])
    assert result.exit_code == 0, result.output


def add_exec_source(
    runner,
    path,
    name: str,
    argv: Iterable[str],
    *,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
) -> None:
    command = ["new", "source", "exec", name]
    for arg in argv:
        command.extend(["--argv", arg])
    if env:
        for key, value in env.items():
            command.extend(["--env", f"{key}={value}"])
    if cwd:
        command.extend(["--cwd", cwd])
    command.extend(["--jn", str(path)])
    result = runner.invoke(app, command)
    assert result.exit_code == 0, result.output


def add_exec_target(
    runner,
    path,
    name: str,
    argv: Iterable[str],
    *,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
) -> None:
    command = ["new", "target", "exec", name]
    for arg in argv:
        command.extend(["--argv", arg])
    if env:
        for key, value in env.items():
            command.extend(["--env", f"{key}={value}"])
    if cwd:
        command.extend(["--cwd", cwd])
    command.extend(["--jn", str(path)])
    result = runner.invoke(app, command)
    assert result.exit_code == 0, result.output


def add_converter(runner, path, name: str, expr: str) -> None:
    command = ["new", "converter", name, "--expr", expr, "--jn", str(path)]
    result = runner.invoke(app, command)
    assert result.exit_code == 0, result.output


def add_pipeline(runner, path, name: str, steps: Iterable[str]) -> None:
    command = ["new", "pipeline", name]
    for step in steps:
        command.extend(["--steps", step])
    command.extend(["--jn", str(path)])
    result = runner.invoke(app, command)
    assert result.exit_code == 0, result.output
