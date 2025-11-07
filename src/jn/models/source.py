"""Source models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .drivers import CurlSpec, ExecSpec, FileSpec, McpSpec, ShellSpec


class Source(BaseModel):
    """Source definition (emits bytes).

    Adapters handle format boundaries (non-JSON → JSON).
    Currently supported: "jc" for shell command output → JSON.
    """

    name: str
    driver: Literal["exec", "shell", "curl", "file", "mcp"]
    mode: Literal["batch", "stream"] = "stream"
    adapter: str | None = None  # e.g., "jc" for shell output → JSON
    exec: ExecSpec | None = None
    shell: ShellSpec | None = None
    curl: CurlSpec | None = None
    file: FileSpec | None = None
    mcp: McpSpec | None = None


__all__ = ["Source"]
