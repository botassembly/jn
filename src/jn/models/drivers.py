"""Driver specifications shared by sources and targets."""

from __future__ import annotations

from typing import Any, Dict, Literal

from pydantic import BaseModel, Field


class ExecSpec(BaseModel):
    """Exec driver specification (argv-based, safe)."""

    argv: list[str]
    cwd: str | None = None
    env: Dict[str, str] = Field(default_factory=dict)


class ShellSpec(BaseModel):
    """Shell driver specification (requires --unsafe-shell)."""

    cmd: str


class CurlSpec(BaseModel):
    """Curl driver specification for HTTP requests."""

    method: str = "GET"
    url: str
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Any | None = None


class FileSpec(BaseModel):
    """File driver specification for reading/writing files."""

    path: str
    mode: Literal["read", "write"]
    append: bool = False
    create_parents: bool = False
    allow_outside_config: bool = False


class McpSpec(BaseModel):
    """MCP driver specification (external tool shim)."""

    server: str
    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)
    stream: bool = False


__all__ = [
    "CurlSpec",
    "ExecSpec",
    "FileSpec",
    "McpSpec",
    "ShellSpec",
]
