# JN vNext — User Guide (Build your `jn.json` with the CLI)

**One idea:** Never hand‑edit JSON. You use the CLI to *create/edit/remove* definitions, and you run pipelines. That’s it.

---

## Install & prerequisites

**Runtime (Python ≥ 3.9)**

* `typer`, `rich` (CLI UX)
* `pydantic>=2` (typed models)
* `jiter` (optional; partial JSON recovery)

**External binaries**

* `jq` (required) — transforms
* `jc` (optional) — parse CSV/TSV/logs/CLI output to JSON/NDJSON
* `curl` (optional) — when using the `curl` driver

**Dev (recommended)**

* `pytest`, `pytest-cov`, `ruff`, `black`, `mypy`, `import-linter`

> Config file resolution precedence: `--jn` path → `JN_PATH` env → `./.jn.json` or `./jn.json` → `~/.jn.json`.

---

## Zero‑to‑config

```bash
# 1) Create a starter config file in the current dir
jn init                 # writes ./jn.json

# 2) See the inventory
jn list sources|targets|converters|pipelines
```

> Tip: You can pass an explicit config via `--jn /path/to/jn.json` on any command.

---

## Add building blocks (no JSON editing!)

Below are the **vNext** CLI commands for *authoring* your `jn.json`. Each `jn new …` writes to the current config file and validates it.

### 1) Sources

#### Exec source (prints two JSON lines)

```bash
jn new source echo.ndjson \
  --driver exec \
  --argv python -c "import json;print(json.dumps({'x':1}));print(json.dumps({'x':2}))"
```

#### File source (reads a file’s bytes)

```bash
jn new source file.read.homes \
  --driver file --path data/homes.csv --mode read
```

#### Curl source (HTTP GET)

```bash
jn new source http.github.repos \
  --driver curl \
  --method GET \
  --url "https://api.github.com/users/${params.user}/repos" \
  --param user:example
```

### 2) Converters

#### jq converter (pass‑through)

```bash
jn new converter jq.pass --engine jq --expr '.'
```

#### jc converter (CSV → NDJSON) — streaming

```bash
jn new converter csv.parse \
  --engine jc --parser csv-s --opt -qq --unbuffer
```

#### jiter converter (salvage truncated JSON)

```bash
jn new converter json.recover \
  --engine jiter --partial-mode trailing-strings --tail-kib 256
```

### 3) Targets

#### Exec target (cat stdin to stdout)

```bash
jn new target sink.cat --driver exec --argv python -c "import sys;print(sys.stdin.read(), end='')"
```

#### File target (write stream to a file atomically)

```bash
jn new target file.write.out \
  --driver file --path out/out.ndjson --mode write --create-parents
```

#### Curl target (HTTP POST JSON)

```bash
jn new target http.post \
  --driver curl --method POST --url https://httpbin.org/post \
  --header 'Content-Type: application/json'
```

### 4) Pipelines (wire them linearly)

```bash
jn new pipeline echo_to_cat \
  --steps \
    source:echo.ndjson \
    converter:jq.pass \
    target:sink.cat
```

CSV example:

```bash
jn new pipeline homes_csv_to_json \
  --steps \
    source:file.read.homes \
    converter:csv.parse \
    converter:jq.pass \
    target:file.write.out
```

---

## Explore & inspect

```bash
# Show the resolved plan (after param/env interpolation)
jn explain echo_to_cat --show-commands --show-env

# Show a single item’s raw JSON (read-only)
jn show source echo.ndjson
```

**Example `jn explain` (abbrev):**

```json
{
  "pipeline": "homes_csv_to_json",
  "steps": [
    {"type":"source","name":"file.read.homes","driver":"file","path":"data/homes.csv"},
    {"type":"converter","name":"csv.parse","engine":"jc","raw":false,"modules":null},
    {"type":"target","name":"file.write.out","driver":"file","path":"out/out.ndjson"}
  ]
}
```

---

## Run

```bash
# Plain run
jn run echo_to_cat

# With params and env overrides
jn --env API_TOKEN=xyz run http_to_post --param user=octocat
```

**Streaming guarantee:** JN connects processes with OS pipes; no Python buffering on the hot path. For non‑streaming stages, JN uses a bounded buffer with a hard cap to avoid surprises.

---

## Edit / remove

```bash
# Open your editor on a definition (safe; JN validates on save)
jn edit source echo.ndjson

# Remove an item by name
jn rm converter csv.parse
```

---

## End‑to‑end example (CSV → JSONL file)

```bash
# Seed a config and CSV
jn init
mkdir -p data out && printf 'a,b\n1,2\n3,4\n' > data/homes.csv

# Add blocks
jn new source file.read.homes --driver file --path data/homes.csv --mode read
jn new converter csv.parse --engine jc --parser csv-s --opt -qq --unbuffer
jn new target file.write.out --driver file --path out/out.ndjson --mode write --create-parents
jn new pipeline homes_csv_to_json --steps source:file.read.homes converter:csv.parse target:file.write.out

# Inspect then run
jn explain homes_csv_to_json --show-commands
jn run homes_csv_to_json
cat out/out.ndjson
```

**Output (`out/out.ndjson`):**

```ndjson
{"a":"1","b":"2"}
{"a":"3","b":"4"}
```

---

## JSON snapshots (for reference only)

You shouldn’t hand‑edit these, but this is what the CLI writes.

```json
{
  "version": "0.1",
  "name": "demo",
  "sources": [
    {"name":"file.read.homes","driver":"file","file":{"path":"data/homes.csv","mode":"read"}}
  ],
  "converters": [
    {"name":"csv.parse","engine":"jc","jc":{"parser":"csv-s","opts":["-qq"],"unbuffer":true}},
    {"name":"jq.pass","engine":"jq","expr":"."}
  ],
  "targets": [
    {"name":"file.write.out","driver":"file","file":{"path":"out/out.ndjson","mode":"write","append":false}}
  ],
  "pipelines": [
    {"name":"homes_csv_to_json","steps":[
      {"type":"source","ref":"file.read.homes"},
      {"type":"converter","ref":"csv.parse"},
      {"type":"target","ref":"file.write.out"}
    ]}
  ]
}
```

---

## Cheat sheet

```
jn init
jn list <sources|targets|converters|pipelines>
jn new source <name> [--driver exec|shell|curl|file|mcp] [...]
jn new converter <name> [--engine jq|jc|jiter|delimited] [...]
jn new target <name> [--driver exec|shell|curl|file|mcp] [...]
jn new pipeline <name> --steps source:S [converter:C ...] target:T
jn explain <pipeline> [--show-commands] [--show-env]
jn run <pipeline> [--param k=v] [--env K=V]
jn edit <kind> <name>
jn rm <kind> <name>
```

That’s the entire surface: **author with CLI → inspect → run.**

