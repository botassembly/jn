"""Target models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .drivers import CurlSpec, ExecSpec, FileSpec, McpSpec, ShellSpec


class Target(BaseModel):
    """Target definition (consumes bytes)."""

    name: str
    driver: Literal["exec", "shell", "curl", "file", "mcp"]
    mode: Literal["batch", "stream"] = "stream"
    exec: ExecSpec | None = None
    shell: ShellSpec | None = None
    curl: CurlSpec | None = None
    file: FileSpec | None = None
    mcp: McpSpec | None = None


__all__ = ["Target"]
