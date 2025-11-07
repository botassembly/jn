# JN vNext — Architecture & Bootstrap Plan

**Goal:** keep the CLI paper-thin while concentrating all stateful work in the config layer. The CLI parses arguments, hands them to `jn.config`, and prints results. Configuration loading, mutation, and pipeline execution all happen inside the config package so callers never juggle Pydantic models directly.

---

## 1) Guiding principles

* **CLI is thin** – each command has ≤3 imports and defers to `jn.config` helpers.
* **Clear layering** – `jn.cli → jn.config → jn.home`; `jn.models` contains the shared Pydantic types.
* **Single config entry point** – `from jn import config`; call `config.set_config_path()` once per command, then use the module API (list/add/run) without touching raw models.
* **Typed config** – shallow Pydantic models for Config/Source/Target/Converter/Pipeline; validation stays in the model layer.
* **Binary-safe streaming** – pipeline execution only pushes bytes through subprocess pipes; no Python buffering on the hot path.

---

## 2) Directory layout

```
src/jn/
  __init__.py            # re-export Typer app and config facade
  options.py             # shared Typer option definitions (ConfigPath)
  cli/
    __init__.py          # Typer app wiring (no logic)
    init.py              # creates jn.json skeleton
    list.py              # list names by collection
    explain.py           # resolve plan, optional env/command dumps
    run.py               # execute pipeline via config.run_pipeline
    new/
      __init__.py        # `jn new ...` command group registration
      source.py          # `jn new source <driver>` subcommands
      target.py          # `jn new target <driver>` subcommands
      converter.py       # `jn new converter`
      pipeline.py        # `jn new pipeline`
    show/
      __init__.py        # `jn show ...` group wiring
      source.py|target.py|converter.py|pipeline.py  # read-only inspectors
  config/
    __init__.py          # public facade (set_config_path, list/add/run/explain)
    core.py              # global state cache + persistence
    catalog.py           # read-only helpers (names/lookups)
    mutate.py            # add_* helpers for sources/targets/etc.
    pipeline.py          # explain/run helpers bound to active config
    types.py             # shared Literal types for collections
    utils.py             # CLI parsing helpers (env parsing, etc.)
  home/
    __init__.py, io.py   # path resolution + JSON read/write (no Pydantic)
  models/
    __init__.py          # exports Config/Source/Target/Converter/Pipeline
    config.py, source.py, target.py, converter.py, pipeline.py, drivers.py, errors.py
  drivers/
    __init__.py, exec.py # subprocess spawning utilities
```

**Tests** (outside-in only)

```
tests/
  integration/           # Typer CliRunner flows exercising public CLI
  data/                  # sample fixtures for pipelines
```

---

## 3) Config resolution & public API

**Precedence**

1. CLI `--jn /path/to/jn.json`
2. `JN_PATH` environment variable
3. Current working directory: `./.jn.json` then `./jn.json`
4. Home directory fallback: `~/.jn.json`

**Top-level API**

```python
from jn import config

config.set_config_path(cli_path)
config.add_source("echo", "exec", argv=["python", "-c", "print('hi')"])
config.add_converter("pass", expr=".")
config.add_target("cat", "exec", argv=["cat"])
config.add_pipeline("demo", ["source:echo", "converter:pass", "target:cat"])
config.run_pipeline("demo")
```

The facade keeps a cached `Config` model plus the active path. `config.reset()` clears the cache (used in tests). Mutations validate through Pydantic before persisting back to disk via `jn.home.save_json()`.

**Home layer (pure IO + path finding)**

```python
from pathlib import Path
from jn.home import resolve_config_path, load_json, save_json

path = resolve_config_path(cli_path)
config_dict = load_json(path)
# ...
save_json(path, config_dict)
```

---

## 4) Models (Pydantic, strict & tiny)

Each collection lives in its own file under `jn.models`. Examples:

* `models/config.py` – root `Config` model + uniqueness validators.
* `models/source.py` – driver-specific models (exec/shell/curl/file) with strict typing.
* `models/converter.py` – jq converter model (`expr`, `file`, `modules`, `raw`). **NOTE: jq is the ONLY converter (JSON → JSON transformation)**.
* `models/target.py` – mirrors `Source` with driver metadata.
* `models/pipeline.py` – pipeline steps and plan models used by `explain`.
* `models/adapters.py` (future) – source adapters (e.g., jc for shell → JSON) and target adapters (JSON → other formats).

All models enforce name uniqueness and minimal validation; business rules stay in the config layer helpers.

---

## 5) Adapters (source & target wrappers)

**Source adapters** wrap non-JSON outputs and convert them to JSON/NDJSON so converters can process them:

* **jc adapter** – wraps shell command output using jc's registered parsers (dig, ls, ps, etc.)
  - Can use "magic" syntax: `jc <command>` instead of `<command> | jc --<parser>`
  - Registered parsers map commands to jc formatters
  - Example: `jc dig example.com` → JSON output

**Target adapters** (future) would convert JSON to other formats when targets require non-JSON input.

**Key principle:** Adapters are NOT converters. Converters (jq) only do JSON → JSON transformations. Adapters handle format boundaries (non-JSON ↔ JSON).

**Pipeline flow with adapters:**
```
Source (exec/shell/curl/file)
  ↓
[optional source adapter: jc for shell output]
  ↓
Converter (jq: JSON → JSON)
  ↓
[optional target adapter: future JSON → other formats]
  ↓
Target (exec/shell/curl/file)
```

---

## 6) Pipeline execution

`config.pipeline.run_pipeline()` currently supports the `exec` driver for sources/targets and jq converters. Each stage spawns subprocesses via `jn.drivers.spawn_exec`, streams bytes, and raises `JnError` on non-zero exits. `config.pipeline.explain_pipeline()` builds a read-only `PipelinePlan` with optional `--show-commands` and `--show-env` enrichment for CLI callers.

---

## 7) Testing discipline

* Write outside-in tests under `tests/integration/` using Typer's `CliRunner`.
* Tests set `--jn` explicitly (or rely on fixtures) so they never import config internals directly.
* `make check` runs formatting, linting, type-checking, and import-linter contracts.
* `make test` executes pytest through UV; coverage currently tracks integration flows end-to-end.

