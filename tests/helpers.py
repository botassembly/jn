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
    """Add a pipeline with new simplified syntax.

    Steps should be in format ["source:name", "converter:name", "target:name"].
    """
    command = ["new", "pipeline", name]

    # Parse steps and build command with new flags
    source_name = None
    converter_names = []
    target_name = None

    for step in steps:
        step_type, step_ref = step.split(":", 1)
        if step_type == "source":
            source_name = step_ref
        elif step_type == "converter":
            converter_names.append(step_ref)
        elif step_type == "target":
            target_name = step_ref

    # Build command with new flags
    if source_name:
        command.extend(["--source", source_name])
    for conv_name in converter_names:
        command.extend(["--converter", conv_name])
    if target_name:
        command.extend(["--target", target_name])

    command.extend(["--jn", str(path)])
    result = runner.invoke(app, command)
    assert result.exit_code == 0, result.output
