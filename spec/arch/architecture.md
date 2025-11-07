# JN vNext — Architecture & Bootstrap Plan

**Goal:** replace the messy codebase with a tiny, well‑layered CLI that: (1) parses args and delegates, (2) centralizes config, (3) uses typed models, (4) keeps imports minimal in CLI files, and (5) is easy to test end‑to‑end.

---

## 1) Guiding principles

* **CLI is thin**: each command has 2–3 imports, does arg parsing + 3–4 service calls max.
* **Clear layering**: `jn.cli → jn.service → jn.home`. `jn.models` is shared by all.
* **Config as a top‑level module**: `from jn import config` → `get_config()/set_config()` with precedence and testability.
* **Typed project**: Pydantic models for `Project/Source/Target/Converter/Pipeline` (compact, strict).
* **Simple exceptions**: raise `JnError(step, name, exit_code, stderr=...)`; CLI prints either human hints or JSON envelopes.
* **Binary‑safe streaming**: only read/write bytes on STDIN/STDOUT.

---

## 2) Directory layout (single top‑level `src/`)

```
src/jn/
  __init__.py
  config.py              # global get/set/reset; resolves jn.json via home
  home/
    __init__.py          # path resolution + file IO only (no Pydantic here)
  models/
    __init__.py
    project.py           # Pydantic models + validators
  service/
    __init__.py
    pipeline.py          # plan + run (executes source → converters → target)
    explain.py           # build resolved plan for display
    spawn.py             # one subprocess helper (exec/shell/curl/jq)
  cli/
    __init__.py          # Typer app wiring (no logic)
    init.py              # creates example jn.json
    list.py              # lists names by kind
    explain.py           # prints resolved plan (optionally commands/env)
    run.py               # minimal: parse, get_config, service.run
    source.py            # `source run` (thin)
    target.py            # `target run` (thin)
    convert.py           # `convert` (thin)
```

**Tests** (outside‑in):

```
tests/
  unit/cli/…             # 1–2 tests per command via Typer CliRunner
  integration/…          # e2e pipelines w/ exec + jq goldens
  data/, goldens/        # sample fixtures
```

---

## 3) Config resolution & public API

**Precedence**

1. CLI `--jn /path/to/jn.json`
2. `JN_PATH` env var
3. CWD: `.jn.json` **or** `jn.json` (prefer `.jn.json` when both)
4. User home: `~/.jn.json`

**Top‑level API** (for tests & CLI):

```python
# src/jn/config.py
from pathlib import Path
from typing import Optional
from .models.project import Project
from .home import resolve_config_path, load_json

_CONFIG: Optional[Project] = None

def get_config(path: Optional[Path] = None) -> Project:
    """Return a cached Project (load+validate on first use).
    If `path` is given, (re)load from that path and cache it. """
    global _CONFIG
    if path is not None:
        data = load_json(path)
        _CONFIG = Project.model_validate(data)
        return _CONFIG
    if _CONFIG is None:
        p = resolve_config_path()
        data = load_json(p)
        _CONFIG = Project.model_validate(data)
    return _CONFIG

def set_config(project: Project) -> None:
    """Inject a Project (for unit tests)."""
    global _CONFIG
    _CONFIG = project

def reset_config() -> None:
    global _CONFIG
    _CONFIG = None
```

**Home layer** (pure IO + path finding):

```python
# src/jn/home/__init__.py
from pathlib import Path
import os, json

def resolve_config_path(cli_path: Path | None = None) -> Path:
    if cli_path: return cli_path
    env = os.getenv("JN_PATH")
    if env: return Path(env).expanduser()
    cwd = Path.cwd()
    for name in (".jn.json", "jn.json"):
        p = cwd / name
        if p.exists(): return p
    return Path.home() / ".jn.json"

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
```

---

## 4) Models (Pydantic, strict & tiny)

Add dependency: `pydantic>=2`.

```python
# src/jn/models/project.py
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional, Union, List, Dict, Any

class ExecSpec(BaseModel):
    argv: List[str]
    cwd: Optional[str] = None
    env: Dict[str, str] = Field(default_factory=dict)

class ShellSpec(BaseModel):
    cmd: str

class CurlSpec(BaseModel):
    method: str = "GET"
    url: str
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Any] = None  # "stdin" | str | dict

Driver = Union[ExecSpec, ShellSpec, CurlSpec]

class Source(BaseModel):
    name: str
    driver: Literal["exec","shell","curl"]
    mode: Literal["batch","stream"] = "batch"
    exec: Optional[ExecSpec] = None
    shell: Optional[ShellSpec] = None
    curl: Optional[CurlSpec] = None

class Target(Source):
    pass

class Converter(BaseModel):
    name: str
    engine: Literal["jq"] = "jq"
    expr: Optional[str] = None
    file: Optional[str] = None
    modules: Optional[str] = None
    raw: bool = False
    args: Dict[str, Any] = Field(default_factory=dict)

class Step(BaseModel):
    type: Literal["source","converter","target"]
    ref: str
    args: Dict[str, Any] = Field(default_factory=dict)

class Pipeline(BaseModel):
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    steps: List[Step]

class Project(BaseModel):
    version: str
    name: str
    sources: List[Source] = Field(default_factory=list)
    targets: List[Target] = Field(default_factory=list)
    converters: List[Converter] = Field(default_factory=list)
    pipelines: List[Pipeline] = Field(default_factory=list)

    @field_validator("sources","targets","converters","pipelines")
    @classmethod
    def names_unique(cls, v):
        names = [x.name for x in v]
        assert len(names) == len(set(names)), "duplicate names are not allowed"
        return v
```

---

## 5) Service layer (single spawn helper + tiny entrypoints)

**Error type:**

```python
# src/jn/service/__init__.py
from dataclasses import dataclass
@dataclass
class JnError(Exception):
    step: str
    name: str
    exit_code: int
    stderr: str | None = None
```

**One subprocess helper (keeps logic out of CLI):**

```python
# src/jn/service/spawn.py
import subprocess, json, sys
from typing import Mapping, Optional
from ..models.project import ExecSpec, ShellSpec, CurlSpec

BUF = sys.stdout.buffer

def write(data: bytes) -> None:
    BUF.write(data); BUF.flush()

def run_exec(spec: ExecSpec, stdin: Optional[bytes]=None):
    return subprocess.run(spec.argv, input=stdin, cwd=spec.cwd,
                          env=(None if not spec.env else {**spec.env, **{}}),
                          check=False, capture_output=True)

def run_shell(spec: ShellSpec, stdin: Optional[bytes]=None):
    return subprocess.run(spec.cmd, input=stdin, shell=True, check=False, capture_output=True)

def run_curl(spec: CurlSpec, stdin: Optional[bytes]=None):
    args = ["curl","-sS","-X", spec.method, spec.url]
    for k,v in (spec.headers or {}).items(): args += ["-H", f"{k}: {v}"]
    if spec.body == "stdin" and stdin is not None:
        args += ["--data-binary","@-"]
        return subprocess.run(args, input=stdin, check=False, capture_output=True)
    if isinstance(spec.body, (dict, list)):
        args += ["--data", json.dumps(spec.body)]
    elif isinstance(spec.body, str) and spec.body:
        args += ["--data", spec.body]
    return subprocess.run(args, check=False, capture_output=True)
```

**Pipeline run (no arg parsing here):**

```python
# src/jn/service/pipeline.py
from typing import Dict, Any
from ..models.project import Project, Converter
from . import JnError
from .spawn import run_exec, run_shell, run_curl, write
import subprocess, tempfile, os

def _run_source(src, params: Dict[str, Any]) -> bytes:
    if src.driver == "exec":
        return run_exec(src.exec).stdout
    if src.driver == "shell":
        return run_shell(src.shell).stdout
    if src.driver == "curl":
        return run_curl(src.curl).stdout
    raise NotImplementedError(src.driver)

def _run_converter(conv: Converter, stdin: bytes) -> bytes:
    # jq only; respect raw/file/expr/modules/args
    from ..util import run_jq
    res = run_jq(expr=conv.expr, file=conv.file, modules=conv.modules,
                 args=conv.args, raw=conv.raw, input_data=stdin)
    if res.returncode != 0:
        raise JnError("converter", conv.name, res.returncode, res.stderr.decode("utf-8","ignore"))
    return res.stdout

def _run_target(tgt, stdin: bytes) -> bytes:
    if tgt.driver == "exec":
        return run_exec(tgt.exec, stdin).stdout
    if tgt.driver == "shell":
        return run_shell(tgt.shell, stdin).stdout
    if tgt.driver == "curl":
        from copy import deepcopy
        spec = deepcopy(tgt.curl); spec.body = spec.body or "stdin"
        return run_curl(spec, stdin).stdout
    raise NotImplementedError(tgt.driver)

def run_pipeline(pr: Project, pipe_name: str, params: Dict[str, Any]) -> bytes:
    pipe = next((p for p in pr.pipelines if p.name == pipe_name), None)
    if not pipe: raise KeyError(f"pipeline not found: {pipe_name}")
    # source
    src = next(s for s in pr.sources if s.name == pipe.steps[0].ref)
    out = _run_source(src, pipe.steps[0].args or {})
    # converters
    for step in pipe.steps[1:-1]:
        conv = next(c for c in pr.converters if c.name == step.ref)
        out = _run_converter(conv, out)
    # target
    tgt = next(t for t in pr.targets if t.name == pipe.steps[-1].ref)
    out = _run_target(tgt, out)
    return out
```

---

## 6) CLI shape (minimal imports; delegates to service)

**Run command (example)** — *imports ≤3 in the file*

```python
# src/jn/cli/run.py
import typer
from ..config import get_config
from .common import resolve_params
from ..service.pipeline import run_pipeline

def register(app: typer.Typer) -> None:
    @app.command()
    def run(pipeline: str, param: list[str] = typer.Option([], "--param")) -> None:
        pr = get_config()
        args = resolve_params(param)
        out = run_pipeline(pr, pipeline, args)
        import sys; sys.stdout.buffer.write(out)
```

**Other commands** (`explain`, `list`, `init`, `source run`, `target run`, `convert`) follow the same pattern: parse → `get_config()` → call service → write bytes.

---

## 7) Import Linter

`.importlinter` (strict layering + forbid upwards):

```ini
[importlinter]
root_package=jn
include_external_packages=False

[importlinter:contract:layers]
name=CLI -> Service -> Home layering
type=layers
layers=
    jn.cli
    jn.service
    jn.home

[importlinter:contract:home_no_upwards]
name=Home remains independent (no upward imports)
type=forbidden
source_modules=
    jn.home
forbidden_modules=
    jn.cli
    jn.service
```

---

## 8) Tests (1–2 per CLI endpoint)

Use `Typer`’s `CliRunner` and offline `exec`/`jq` fixtures. Examples:

* **`test_run_exec_pipeline.py`**: small exec source → jq pass‑through → exec cat target; assert 2 JSON lines.
* **`test_convert_jsonl_strict.py`**: mixed NDJSON → `jsonl.strict` → only objects remain.
* **`test_explain_prints_plan.py`**: `jn explain p --show-commands --show-env` returns compact JSON with `argv/cmd/raw`.
* **`test_init_writes_file.py`**: `jn init` creates `jn.json`; refuses overwrite.
* **`test_source_run_stub_env.py`**: `JN_STUB_<NAME>` path yields deterministic bytes (no external calls).

**Policy:**

* Tests are **outside‑in** only; no unit tests for subprocess details.
* 1–2 tests **per CLI command**; keep fixtures tiny; no network calls.

---

## 9) Makefile & deps

**Dependencies** (additions):

* `pydantic>=2` (models)

**Makefile**: keep your existing targets. Ensure `lint-imports` runs Import Linter:

```
lint-imports:
	uv run lint-imports --config .importlinter
```

---

## 10) Minimal CLI contract (for the new dev)

```
jn init [--jn PATH]
jn list <sources|targets|converters|pipelines> [--jn PATH]
jn explain <pipeline> [--param k=v] [--jn PATH] [--show-commands] [--show-env]
jn run <pipeline> [--param k=v] [--jn PATH]
jn source run <name> [--param k=v] [--jn PATH]
jn target run <name> [--jn PATH]
jn convert <name> [--param k=v] [--jn PATH]
```

Each command does: **parse → get_config() → service → write bytes**. No business logic in CLI.

---

## 11) Acceptance checklist (ship when all pass)

* [ ] CLI files ≤3 imports; no subprocess logic in CLI.
* [ ] `jn.config` exposes `get_config()`/`set_config()` and precedence works.
* [ ] Models validate `jn.json`; duplicate names rejected.
* [ ] `run_pipeline` honors converter `.raw` and produces identical behavior to `convert`.
* [ ] All subprocess IO is **bytes**; no lossy text decoding.
* [ ] Import Linter passes: layers + forbid upwards from `home`.
* [ ] 1–2 passing tests per CLI command; coverage ≥70%.

---

## 12) Day‑0 refactor plan (copy/paste tasks)

1. **Scaffold** `jn.config`, `jn.home`, `jn.models`, `jn.service.spawn`.
2. **Move** pipeline/explain logic into `jn.service.*` (no Typer imports there).
3. **Slim** CLI modules to ≤30 lines each; wire through `register(app)` only.
4. **Add** Pydantic; validate on `get_config()`; remove ad‑hoc dict access.
5. **Replace** any text streaming with `sys.stdout.buffer.write()`.
6. **Unify** jq invocation in one place and honor `raw/modules/args` consistently.
7. **Fix** `.importlinter`; add `make lint-imports` task.
8. **Write** the 7 minimal CLI tests + 2 integration pipeline tests.

---

## 13) Example `jn.json` (tiny, offline‑friendly)

```json
{
  "version": "0.1",
  "name": "demo",
  "sources": [
    {"name": "echo.ndjson", "driver": "exec", "exec": {"argv": ["python", "-c", "import json;print(json.dumps({'x':1}));print(json.dumps({'x':2}))"]}}
  ],
  "converters": [
    {"name": "passthrough", "engine": "jq", "expr": "."}
  ],
  "targets": [
    {"name": "sink.cat", "driver": "exec", "exec": {"argv": ["python", "-c", "import sys; print(sys.stdin.read(), end='')"]}}
  ],
  "pipelines": [
    {"name": "echo_to_cat", "steps": [
      {"type": "source", "ref": "echo.ndjson"},
      {"type": "converter", "ref": "passthrough"},
      {"type": "target", "ref": "sink.cat"}
    ]}
  ]
}
```

---

**This is the blueprint.** Hand it to a new dev and they can scaffold the project quickly, keep the CLI feather‑weight, and enforce clean boundaries from day one.

---

## Addendum A — Parsers, Bridges, and Streaming Guarantees

This addendum specifies **how to support `jc`, MCP tools, files, delimited text (CSV/TSV)**, guaranteed **streaming execution**, and **partial JSON recovery with `jiter`**—all without bloating the CLI or breaking layering.

### A1) `jc` support (CLI/file → JSON parser wrappers)

**Intent:** Use `jc` to turn non‑JSON command/file output into JSON/NDJSON **before** jq transforms.

**Design choices**

* Keep the CLI thin; **no new top‑level commands** required. We introduce a **converter engine alias** and a recommended **exec wrapper**.
* Two ways to integrate:

  1. **Sugar converter**: `converter.engine: "jc"` → resolves to `exec` argv.
  2. **Direct exec** (preferred for power users): `driver: exec` with explicit `argv`.

**Spec (sugar form):**

```json
{
  "name": "csv.parse",
  "engine": "jc",
  "jc": {
    "parser": "csv-s",              // any jc parser; use *-s for stream
    "opts": ["-q"],                  // e.g., -qq to ignore streaming parse errors
    "unbuffer": true                 // maps to jc -u to reduce latency
  }
}
```

**Resolution → exec argv:** `jc [-u] <opts…> --<parser>`

**Examples**

* Parse `dig` → JSON, then jq:

```json
{"type":"source","ref":"shell.dig"}
{"type":"converter","ref":"jc.dig"}
{"type":"converter","ref":"jq.pick"}
```

* CSV file → NDJSON → jq:

```json
{"type":"source","ref":"file.homes.csv"}
{"type":"converter","ref":"csv.parse"}
{"type":"converter","ref":"jq.normalize"}
```

**Streaming rules**

* Prefer **streaming parsers** (`*-s`) + `-u` (unbuffer) when low‑latency is needed.
* When using non‑streaming `jc` parsers, mark the step `mode:"batch"` (the planner will warn; see A5).

**Failure policy**

* Recommend `opts: ["-qq"]` for long‑lived streams. Downstream can drop failures:
  `jq 'select(._jc_meta.success // true)'`.

---

### A2) MCP support (Model Context Protocol)

**Intent:** Call MCP tools as sources/targets **via exec**, keeping JN stateless and deterministic.

**Drivers**

* **`driver: exec`** calling an **`mcp-client`** shim (small binary/script you control) that speaks MCP over stdio.
* Optional sugar: `driver: "mcp"` that compiles to the same exec argv.

**Source wrapper (request → JSON response)**

```json
{
  "name": "mcp.github.search",
  "driver": "mcp",
  "mcp": {
    "server": "github",
    "tool": "search_repos",
    "args": {"query": "${params.q}"},
    "stream": true                   // client emits NDJSON frames
  }
}
```

**Target wrapper (send JSON to a tool)**

```json
{
  "name": "mcp.salesforce.update",
  "driver": "mcp",
  "mcp": {"server": "sf", "tool": "update_record", "args": {}}
}
```

**Scaffold/import**

* `jn mcp import <server>` → generates `sources/targets` from a server’s tool list into project or `~/.local/jn/servers/<name>/…` with **param stubs only** (no giant schemas).
* `explain --show-commands` always shows the **final argv/env**; secrets must only come from CLI `--env` or step‑local `env`.

**Streaming**

* If the shim can translate MCP **progress/streaming** events into NDJSON frames, set `stream:true`. Otherwise the step is `mode:"batch"`.

---

### A3) File support (read/write with zero surprises)

**Drivers**

* `driver: file` — implemented **in‑process** for portability and speed.

**Source**

```json
{
  "name": "file.read.homes",
  "driver": "file",
  "file": { "path": "${params.path}", "mode": "read" }
}
```

* Reads bytes from `path` and streams to stdout.
* Paths support `${params.*}` and `${env.*}` interpolation.

**Target**

```json
{
  "name": "file.write.out",
  "driver": "file",
  "file": { "path": "${params.path}", "mode": "write", "append": false }
}
```

* Writes stdin bytes to `path` (atomically via temp+rename when possible).

**Safety knobs**

* Optional `allow_outside_project: false` to confine paths to the project dir.
* `create_parents: true` to `mkdir -p` safely.

---

### A4) Delimited text (CSV, TSV, etc.)

**Preferred**: `jc` parsers for CSV (use `csv-s`), and other formats `jc` supports.

**CSV via `jc`**

```json
{ "name": "csv.parse", "engine": "jc", "jc": { "parser": "csv-s" } }
```

**TSV and generic delimited (fallback)**

* Add a tiny built‑in converter `engine: "delimited"` using Python’s `csv` module in **streaming** mode.

```json
{
  "name": "tsv.parse",
  "engine": "delimited",
  "delimited": { "delimiter": "	", "has_header": true, "quotechar": "\"" }
}
```

* Emits **NDJSON objects**, one per row. For no header: provide `fields: ["c1","c2",…]`.

**Pipelines**

```json
{"type":"source","ref":"file.read.homes"}
{"type":"converter","ref":"csv.parse"}
{"type":"converter","ref":"jq.shape"}
{"type":"target","ref":"file.write.out"}
```

---

### A5) Streaming guarantees (chain, don’t buffer)

**Contract**

* The planner builds a **connected Popen chain**: `source.stdout → conv1.stdin → … → target.stdin`.
* CLI never decodes or accumulates payloads; only **bytes** flow.
* Stages advertise `mode: "stream" | "batch"`. The orchestrator:

  * connects streams for `stream` stages,
  * for `batch` stages, isolates them and forwards their whole result to the next stage (with a **hard cap** `JN_BUFFER_LIMIT_BYTES`, default 256 MiB, to avoid surprises).

**Flags & behavior**

* `jq` is invoked with `-c` and respects NDJSON streaming by default.
* `jc` streaming parsers use `-u` + `-qq` when requested.
* We print compact flow stats on completion: `src: N rec | jc: N rec | jq: N rec | tgt: N rec (t=1.2s)`.

**Acceptance**

* 10+ GiB CSV → `jc csv-s` → `jq` → `/dev/null` uses **O(1) memory** (bounded pipes), no Python‑level buffering.

---

### A6) Partial JSON recovery with `jiter`

**Problem**

* Some sources emit a **single JSON document** that may be **truncated** (killed process, log cutoff). We want best‑effort recovery without breaking streaming for normal NDJSON pipelines.

**Converter: `json.recover` (engine: jiter)**

```json
{
  "name": "json.recover",
  "engine": "jiter",
  "jiter": {
    "partial_mode": "off|on|trailing-strings",  // default: off
    "catch_duplicate_keys": false,
    "float_mode": "float|decimal|lossless-float",
    "tail_kib": 256                              // bound memory for salvage
  }
}
```

**Behavior**

* **For NDJSON inputs**: pass through untouched (streaming).
* **For single‑blob JSON inputs**: buffer **only** up to `tail_kib` around the end of the stream; if EOF arrives mid‑object and `partial_mode != off`, call `jiter.from_json(...)` once to salvage the maximal valid prefix. Emit either:

  * the full parsed object (if complete), or
  * the parsed prefix (if `on`), or
  * the parsed prefix **including the last truncated string** (if `trailing-strings`).
* Emit one JSON value (object/array) on stdout; downstream can explode to NDJSON via jq if needed (`jq -c '.[]'`).

**Why this shape?**

* Keeps **true streaming** for line‑oriented flows; accepts bounded buffering **only when you ask** to salvage a broken single JSON payload.

**Tests**

* Truncated JSON with and without `trailing-strings`.
* Duplicate keys rejection when `catch_duplicate_keys: true`.

---

### A7) Minimal schemas & examples

**`converter.engine: "jc"` (sugar) JSON Schema (sketch)**

```json
{
  "type": "object",
  "required": ["name","engine","jc"],
  "properties": {
    "engine": {"const": "jc"},
    "jc": {
      "type": "object",
      "required": ["parser"],
      "properties": {
        "parser": {"type": "string"},
        "opts": {"type": "array", "items": {"type": "string"}},
        "unbuffer": {"type": "boolean"}
      }
    }
  }
}
```

**`driver: "file"` JSON Schema (sketch)**

```json
{
  "type": "object",
  "required": ["name","driver","file"],
  "properties": {
    "driver": {"const": "file"},
    "file": {
      "type": "object",
      "required": ["path","mode"],
      "properties": {
        "path": {"type": "string"},
        "mode": {"enum": ["read","write"]},
        "append": {"type": "boolean"},
        "create_parents": {"type": "boolean"},
        "allow_outside_project": {"type": "boolean"}
      }
    }
  }
}
```

---

### A8) Developer checklist (to implement this addendum)

1. **Engines & drivers**

   * Implement `engine: jc` (sugar → exec argv) and `engine: delimited` (streaming Python `csv`).
   * Implement `engine: jiter` converter (`json.recover`).
   * Implement `driver: file` (read/write, streaming).
   * Add optional `driver: mcp` sugar → exec argv.
2. **Planner & runner**

   * Add stage `mode` detection: `stream` vs `batch`; enforce pipe chaining for `stream`.
   * Set `JN_BUFFER_LIMIT_BYTES` (env) and error when exceeded in batch stages.
3. **UX**

   * `explain --show-commands --show-env` shows resolved `jc/mcp` argv.
   * Print compact flow stats on completion.
4. **Tests**

   * 1–2 outside‑in tests per new engine/driver (jc csv‑s, delimited TSV, file read/write, jiter trailing‑strings, mcp shim happy path).

**Non‑goals:** No embedded MCP client in JN, no schema‑heavy tool mirrors, no DAG/orchestrator features.

— End Addendum A —

