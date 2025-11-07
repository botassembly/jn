"""Pydantic models for jn.json configuration."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Completed(BaseModel):
    """Result of a subprocess execution."""

    returncode: int
    stdout: bytes
    stderr: bytes


class ExecSpec(BaseModel):
    """Exec driver specification (argv-based, safe)."""

    argv: List[str]
    cwd: Optional[str] = None
    env: Dict[str, str] = Field(default_factory=dict)


class ShellSpec(BaseModel):
    """Shell driver specification (requires --unsafe-shell)."""

    cmd: str


class CurlSpec(BaseModel):
    """Curl driver specification for HTTP requests."""

    method: str = "GET"
    url: str
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Any] = None


class FileSpec(BaseModel):
    """File driver specification for reading/writing files."""

    path: str
    mode: Literal["read", "write"]
    append: bool = False
    create_parents: bool = False
    allow_outside_project: bool = False


class McpSpec(BaseModel):
    """MCP driver specification (external tool shim)."""

    server: str
    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)
    stream: bool = False


class Source(BaseModel):
    """Source definition (emits bytes)."""

    name: str
    driver: Literal["exec", "shell", "curl", "file", "mcp"]
    mode: Literal["batch", "stream"] = "stream"
    exec: Optional[ExecSpec] = None
    shell: Optional[ShellSpec] = None
    curl: Optional[CurlSpec] = None
    file: Optional[FileSpec] = None
    mcp: Optional[McpSpec] = None


class Target(BaseModel):
    """Target definition (consumes bytes)."""

    name: str
    driver: Literal["exec", "shell", "curl", "file", "mcp"]
    mode: Literal["batch", "stream"] = "stream"
    exec: Optional[ExecSpec] = None
    shell: Optional[ShellSpec] = None
    curl: Optional[CurlSpec] = None
    file: Optional[FileSpec] = None
    mcp: Optional[McpSpec] = None


class JqConfig(BaseModel):
    """jq converter configuration."""

    expr: Optional[str] = None
    file: Optional[str] = None
    modules: Optional[str] = None
    raw: bool = False
    args: Dict[str, Any] = Field(default_factory=dict)


class JcConfig(BaseModel):
    """jc converter configuration (CLI output to JSON)."""

    parser: str
    opts: List[str] = Field(default_factory=list)
    unbuffer: bool = False


class JiterConfig(BaseModel):
    """jiter converter configuration (partial JSON recovery)."""

    partial_mode: Literal["off", "on", "trailing-strings"] = "off"
    catch_duplicate_keys: bool = False
    tail_kib: int = 256


class DelimitedConfig(BaseModel):
    """Delimited text converter configuration (CSV/TSV)."""

    delimiter: str = ","
    has_header: bool = True
    quotechar: str = '"'
    fields: Optional[List[str]] = None


class Converter(BaseModel):
    """Converter definition (transforms JSON/NDJSON)."""

    name: str
    engine: Literal["jq", "jc", "jiter", "delimited"]
    jq: Optional[JqConfig] = None
    jc: Optional[JcConfig] = None
    jiter: Optional[JiterConfig] = None
    delimited: Optional[DelimitedConfig] = None


class Step(BaseModel):
    """Pipeline step reference."""

    type: Literal["source", "converter", "target"]
    ref: str
    args: Dict[str, Any] = Field(default_factory=dict)


class Pipeline(BaseModel):
    """Pipeline definition (source → converters → target)."""

    name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    steps: List[Step]


class Project(BaseModel):
    """Root jn.json project configuration."""

    version: str
    name: str
    sources: List[Source] = Field(default_factory=list)
    targets: List[Target] = Field(default_factory=list)
    converters: List[Converter] = Field(default_factory=list)
    pipelines: List[Pipeline] = Field(default_factory=list)

    @field_validator("sources", "targets", "converters", "pipelines")
    @classmethod
    def names_unique(cls, v: List[Any]) -> List[Any]:
        """Ensure names are unique within each collection."""
        names = [x.name for x in v]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate names are not allowed")
        return v
