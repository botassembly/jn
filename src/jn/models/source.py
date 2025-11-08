"""Source models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .drivers import CurlSpec, ExecSpec, FileSpec, McpSpec, ShellSpec


class Source(BaseModel):
    """Source definition (emits bytes).

    File sources automatically use JC parsers based on file extension:
    - .csv → csv_s (JC's built-in streaming CSV parser)
    - .tsv → tsv_s (custom streaming TSV parser)
    - .psv → psv_s (custom streaming PSV parser)
    - .yaml, .yml → yaml (JC's built-in YAML parser)
    - .toml → toml (JC's built-in TOML parser)
    - .xml → xml (JC's built-in XML parser)
    """

    name: str
    driver: Literal["exec", "shell", "curl", "file", "mcp"]
    mode: Literal["batch", "stream"] = "stream"
    # Driver specs
    exec: ExecSpec | None = None
    shell: ShellSpec | None = None
    curl: CurlSpec | None = None
    file: FileSpec | None = None
    mcp: McpSpec | None = None


__all__ = ["Source"]
