# JN vNext — Architecture & Bootstrap Plan

**Goal:** replace the messy codebase with a tiny, well‑layered CLI that: (1) parses args and delegates, (2) centralizes config, (3) uses typed models, (4) keeps imports minimal in CLI files, and (5) is easy to test end‑to‑end.

---

## 1) Guiding principles

* **CLI is thin**: each command has 2–3 imports, does arg parsing + 3–4 config helper calls max.
* **Clear layering**: `jn.cli → jn.config → jn.home`. `jn.models` is shared by all.
* **Config as a top‑level module**: `from jn import config` → call `config.set_config_path()` once, then use the module API (list/add/run) without touching raw models.
* **Typed config**: Pydantic models for `Config/Source/Target/Converter/Pipeline` (compact, strict).
* **Simple exceptions**: raise `JnError(step, name, exit_code, stderr=...)`; CLI prints either human hints or JSON envelopes.
* **Binary‑safe streaming**: only read/write bytes on STDIN/STDOUT.

---

## 2) Directory layout (single top‑level `src/`)

```
src/jn/
  __init__.py
  config/
    __init__.py          # facade: set_config_path, list/add/run helpers
    core.py              # global state + persistence
    catalog.py           # read-only helpers (names, lookups)
    mutate.py            # add/update operations for config objects
    pipeline.py          # explain/run pipeline operations
    utils.py             # CLI parsing helpers
  home/
    __init__.py          # path resolution + file IO only (no Pydantic here)
  models/
    __init__.py
    config.py            # Pydantic models + validators
    ... (sources, targets, converters, pipelines split by type)
  cli/
    __init__.py          # Typer app wiring (no logic)
    init.py              # creates example jn.json
    list.py              # lists names by kind
    explain.py           # prints resolved plan (optionally commands/env)
    run.py               # minimal: parse, set_config_path, config.run_pipeline
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
# src/jn/config/__init__.py
from .core import set_config_path, require, config_path, reset
from .catalog import list_items, fetch_item, get_names, has_item
from .mutate import add_source, add_target, add_converter, add_pipeline
from .pipeline import run_pipeline, explain_pipeline

# usage
config.set_config_path(cli_path)
config.add_source("echo", "exec", argv=[...])
config.list_items("sources")
config.run_pipeline("demo")
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
# src/jn/models/config.py
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

class Config(BaseModel):
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

**Config layer responsibilities:**

* `jn.config.core` loads, caches, and persists the active `Config` instance. `set_config_path(path)` resolves the location (CLI flag → env → cwd → home) and stores `_CONFIG` / `_CONFIG_PATH` for subsequent helpers.
* `jn.config.catalog` provides ordered-name lookups (`list_items`, `fetch_item`, `get_pipeline`, etc.) without exposing the underlying Pydantic models to the CLI.
* `jn.config.mutate` adds new sources/targets/converters/pipelines by cloning the cached config, re-validating with Pydantic, persisting to disk, and updating the module-level cache.
* `jn.config.pipeline` contains the execution/explain logic. It resolves steps against the cached config, runs subprocesses via `jn.drivers.spawn_exec`, and raises `JnError` on failures so the CLI can surface human-friendly messages.

---

## 6) CLI shape (minimal imports; delegates to config)

**Run command (example)** — *imports ≤3 in the file*

```python
# src/jn/cli/run.py
import sys
import typer

from jn import config

from . import ConfigPath, app


@app.command()
def run(pipeline: str, jn: ConfigPath = None) -> None:
    config.set_config_path(jn)
    out = config.run_pipeline(pipeline)
    sys.stdout.buffer.write(out)
    sys.stdout.buffer.flush()
```

**Other commands** (`explain`, `list`, `init`, `new`, `show`) follow the same pattern: parse → `config.set_config_path()` → call a config helper → write bytes.

---

## 7) Import Linter

`.importlinter` (strict layering + forbid upwards):

```ini
[importlinter]
root_package=jn
include_external_packages=False

[importlinter:contract:layers]
name=CLI -> Config -> Home layering
type=layers
layers=
    jn.cli
    jn.config
    jn.home

[importlinter:contract:home_no_upwards]
name=Home remains independent (no upward imports)
type=forbidden
source_modules=
    jn.home
forbidden_modules=
    jn.cli
    jn.config
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

Each command does: **parse → config.set_config_path() → call config helper → write bytes**. No business logic in CLI.

---

## 11) Acceptance checklist (ship when all pass)

* [ ] CLI files ≤3 imports; no subprocess logic in CLI.
* [ ] `jn.config` exposes `set_config_path()/require()` helpers and precedence works.
* [ ] Models validate `jn.json`; duplicate names rejected.
* [ ] `run_pipeline` honors converter `.raw` and produces identical behavior to `convert`.
* [ ] All subprocess IO is **bytes**; no lossy text decoding.
* [ ] Import Linter passes: layers + forbid upwards from `home`.
* [ ] 1–2 passing tests per CLI command; coverage ≥70%.

---

## 12) Day‑0 refactor plan (copy/paste tasks)

1. **Scaffold** `jn.config` package (`core`, `catalog`, `mutate`, `pipeline`, `utils`) plus `jn.home` and the split `jn.models` modules.
2. **Consolidate** pipeline/explain logic inside `jn.config.pipeline` (no Typer imports there).
3. **Slim** CLI modules to ≤30 lines each; wire through direct Typer commands and call `config.*` helpers.
4. **Add** Pydantic; validate via `config.set_config_path()`/`require()` instead of ad‑hoc dict access.
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

