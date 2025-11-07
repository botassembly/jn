**Goal:** interact with JN only through the CLI. Create and mutate `jn.json` via commands, inspect with `list/show/explain`, and run pipelines end-to-end.

---

## Install & prerequisites

* Python ≥ 3.11 (UV manages the virtualenv).
* External binaries:
  - `jq` (required) — JSON transformation (the only converter engine)
  - `jc` (optional) — Source adapter for shell output → JSON
  - `curl` (optional) — HTTP sources/targets
* Install dependencies with `make install` and keep formatting/tests green with `make check` / `make test`.

> Invoke the CLI via `uv run jn …` when running from a checkout. The published entry point is identical (`jn …`).

---

## 1. Bootstrap a config

```bash
# Create a starter config alongside the working directory
uv run jn init --jn ./jn.json

# Inspect the skeleton
cat jn.json
```

`jn init` refuses to overwrite unless `--force` is provided.

---

## 2. Create building blocks (no JSON editing)

### Sources

```bash
# Exec driver (recommended for deterministic pipelines)
uv run jn new source exec echo-json \
  --jn ./jn.json \
  --argv python \
  --argv -c \
  --argv "import json;print(json.dumps({'msg':'hello'}))"

# Optional environment variables
uv run jn new source exec echo-secret \
  --jn ./jn.json \
  --argv python --argv -c \
  --argv "import json,os;print(json.dumps({'token':os.getenv('TOKEN')}))" \
  --env TOKEN=abc123

# Additional drivers are stubbed out for future work:
#   uv run jn new source shell …
#   uv run jn new source curl …
#   uv run jn new source file …
```

### Converters

**NOTE:** Converters are jq-only. They transform JSON → JSON. For non-JSON sources (shell output, CSV), use source adapters (see `spec/arch/adapters.md`).

```bash
# jq converter (expr or file/module based)
uv run jn new converter pass-through \
  --jn ./jn.json \
  --expr '.'
```

### Targets

```bash
# Exec driver piping stdout
uv run jn new target exec stdout \
  --jn ./jn.json \
  --argv python --argv -c \
  --argv "import sys;sys.stdout.write(sys.stdin.read())"

# Shell/curl/file variants exist but are not executed yet (tracked on the roadmap).
```

### Pipelines

Steps are expressed as `type:name` pairs in execution order.

```bash
uv run jn new pipeline demo \
  --jn ./jn.json \
  --steps source:echo-json \
  --steps converter:pass-through \
  --steps target:stdout
```

---

## 3. Inspect & validate

```bash
# List names by collection
uv run jn list sources --jn ./jn.json
uv run jn list pipelines --jn ./jn.json

# Show the stored JSON definition for an item
uv run jn show source echo-json --jn ./jn.json

# Explain a pipeline without running it
uv run jn explain demo --jn ./jn.json

# Enrich explain output with argv/env details
uv run jn explain demo --jn ./jn.json --show-commands --show-env
```

`explain` emits a `PipelinePlan` JSON document. `--show-commands` includes argv/cmd/url data; `--show-env` surfaces exec driver environment variables.

---

## 4. Run a pipeline

```bash
uv run jn run demo --jn ./jn.json
```

Pipelines stream bytes end-to-end. Today `run` supports the `exec` driver for sources/targets and jq converters. Missing drivers are captured in the roadmap.

---

## 5. Known gaps / next polish

* `run` lacks global `--env` / `--param` overrides.
* Non-`exec` drivers (`shell`, `curl`, `file`, `mcp`) are parsed into the config but not executed yet.
* `jn explain --show-env` returns raw values; secret masking is pending.
* `jn doctor`, `jn edit`, and other management commands remain to be built.

Track progress and upcoming work in `spec/roadmap.md`.

