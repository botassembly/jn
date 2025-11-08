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
    """Curl driver specification for HTTP requests.

    Supports standard HTTP methods with streaming, retries, and auth.
    For sources: typically GET with no body.
    For targets: typically POST/PUT with body="stdin" to stream request.
    """

    method: str = "GET"
    url: str
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Literal["stdin"] | str | None = None
    timeout: int = 30
    follow_redirects: bool = True
    retry: int = 0
    retry_delay: int = 2
    fail_on_error: bool = True  # Fail on HTTP 4xx/5xx


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
