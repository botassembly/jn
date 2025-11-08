"""Target models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .drivers import CurlSpec, ExecSpec, FileSpec, McpSpec, ShellSpec


class Target(BaseModel):
    """Target definition (consumes bytes).

    File targets automatically convert NDJSON to the appropriate format based on file extension:
    - .json → JSON array format (wrapped in square brackets)
    - .jsonl, .ndjson → NDJSON format (one object per line, no wrapping)
    - .csv → CSV format (headers extracted from first record)
    - .yaml, .yml → YAML array format
    - .toml → TOML format (records wrapped in 'records' array)
    - .xml → XML format (records wrapped in root element)
    """

    name: str
    driver: Literal["exec", "shell", "curl", "file", "mcp"]
    mode: Literal["batch", "stream"] = "stream"
    exec: ExecSpec | None = None
    shell: ShellSpec | None = None
    curl: CurlSpec | None = None
    file: FileSpec | None = None
    mcp: McpSpec | None = None


__all__ = ["Target"]
