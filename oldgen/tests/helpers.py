"""Shared CLI helpers for outside-in integration tests.

Updated for simplified registry architecture (apis/filters).
"""

from __future__ import annotations

from jn.cli import app


def init_config(runner, path) -> None:
    """Initialize a new jn.json config file."""
    result = runner.invoke(app, ["init", "--jn", str(path), "--force"])
    assert result.exit_code == 0, result.output


def add_api(
    runner,
    path,
    name: str,
    base_url: str | None = None,
    auth_type: str | None = None,
    token: str | None = None,
    yes: bool = False,
) -> None:
    """Add an API to the registry."""
    command = ["api", "add", name]
    if base_url:
        command.extend(["--base-url", base_url])
    if auth_type:
        command.extend(["--auth", auth_type])
    if token:
        command.extend(["--token", token])
    if yes:
        command.append("--yes")
    command.extend(["--jn", str(path)])
    result = runner.invoke(app, command)
    assert result.exit_code == 0, result.output


def add_filter(runner, path, name: str, query: str, yes: bool = False) -> None:
    """Add a filter to the registry."""
    command = ["filter", "add", name, "--query", query]
    if yes:
        command.append("--yes")
    command.extend(["--jn", str(path)])
    result = runner.invoke(app, command)
    assert result.exit_code == 0, result.output
