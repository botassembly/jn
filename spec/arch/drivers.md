# JN — Drivers

**Scope.** Drivers are small, composable adapters that move bytes in and out of external systems. Service composes drivers into pipelines; drivers never touch config state directly, and they never depend upward on Service or CLI.

## Goals

* **Safety:** argv‑first, shell guarded; explicit env/cwd.
* **Streaming:** default to pipe‑through with O(1) memory.
* **Portability:** Linux/macOS/Windows (incl. WSL); no bash‑isms.
* **Testability:** outside‑in tests with tiny fixtures; no network in CI by default.

## Package layout

```
src/jn/drivers/
  __init__.py
  exec.py      # spawn_exec(argv, env, cwd)
  shell.py     # spawn_shell(cmd, env, cwd, unsafe)
  curl.py      # run_curl(spec)
  file.py      # read_bytes(path)/write_bytes(path, stream=True)
  mcp.py       # spawn_mcp(server, tool, args, stream)
```

**Imports allowed:** `jn.models` + stdlib/third‑party deps only.

---

## Driver interface (uniform contract)

All drivers conform to a minimal interface returning a `Completed` record:

```python
@dataclass
class Completed:
    returncode: int
    stdout: bytes
    stderr: bytes
```

Functions accept **only plain arguments** (no global reads), so Service can inject env/cwd/args explicitly.

---

## Exec driver

**What:** Spawn a process with `argv` (no shell), optional `env`/`cwd`.

```python
# jn/drivers/exec.py
from subprocess import run, PIPE

def spawn_exec(argv: list[str], *, env: dict[str,str]|None=None, cwd: str|None=None) -> Completed:
    p = run(argv, input=None, check=False, cwd=cwd, env=env, capture_output=True)
    return Completed(p.returncode, p.stdout, p.stderr)
```

**Usage (source):**

```json
{"name":"echo.ndjson","driver":"exec","exec":{"argv":["python","-c","import json;print(json.dumps({'x':1}));print(json.dumps({'x':2}))"]}}
```

**Security:** preferred for all integrations.

---

## Shell driver (guarded)

**What:** Run a shell string **only** when the user explicitly opts in.

```python
# jn/drivers/shell.py
from subprocess import run

def spawn_shell(cmd: str, *, env=None, cwd=None, unsafe=False) -> Completed:
    if not unsafe:
        raise RuntimeError("shell driver requires --unsafe-shell")
    p = run(cmd, shell=True, check=False, cwd=cwd, env=env, capture_output=True)
    return Completed(p.returncode, p.stdout, p.stderr)
```

**Policy:** Service must require `--unsafe-shell` in the run context before using this driver.

---

## Curl driver

**What:** HTTP convenience built on `curl` binary. Safer than shelling string HTTP commands.

```json
{"name":"http.get","driver":"curl","curl":{"method":"GET","url":"https://api.example.com/x","headers":{"Accept":"application/json"}}}
```

**Semantics:**

* For targets, default `body: "stdin"` to stream request payload.
* Add `--fail-with-body`, timeouts, and small retry with backoff in Service.

---

## File driver (in‑process, cross‑platform)

**Source:**

```json
{"name":"file.read","driver":"file","file":{"path":"data/in.csv","mode":"read"}}
```

**Target:**

```json
{"name":"file.write","driver":"file","file":{"path":"out/out.ndjson","mode":"write","append":false,"create_parents":true}}
```

**Notes:**

* Reads/writes bytes; no decoding on the hot path.
* Optional confinement to project directory; rejects `..` traversal when enabled.
* Atomic write via temp+rename where supported.

---

## MCP driver (shim)

**What:** Calls an external **`mcp-client`** shim that speaks MCP over stdio.

```json
{"name":"mcp.github.search","driver":"mcp","mcp":{"server":"github","tool":"search_repos","args":{"q":"${params.q}"},"stream":true}}
```

**Resolution:** `driver:"mcp"` is sugar → `exec.argv = ["mcp-client","--server","github","--tool","search_repos","--args",<json>]`.

**Streaming:** If the shim emits NDJSON frames, mark `stream:true` and chain as a streaming stage.

---

## Streaming semantics (all drivers)

* Service connects `stdout`→`stdin` between stages using OS pipes.
* Drivers never decode content; they just move bytes.
* Non‑streaming stages (rare) are bounded by `JN_BUFFER_LIMIT_BYTES` (default 256 MiB).

---

## Error handling

* Drivers do **not** print. They return `(returncode, stdout, stderr)`.
* Service wraps failures in `JnError(step, name, exit_code, stderr)` and emits structured envelopes by default.

---

## Timeouts & retries

* Exec/Shell: per‑step `timeout_seconds` (Service enforces with `communicate(timeout=...)` or `wait` + kill).
* Curl: add `--max-time`, `--retry`, and exponential backoff (small, capped) at the Service layer.

---

## Cross‑platform

* Avoid `/bin/sh` assumptions; on Windows, rely on `argv` and built‑ins.
* File paths normalized with `pathlib`.
* Tests avoid `bash -lc` (use Python one‑liners for exec examples).

---

## JSON schema (sketch)

```json
{
  "oneOf": [
    {"type":"object","required":["driver","exec"],  "properties":{"driver":{"const":"exec"},  "exec":{"type":"object","required":["argv"],"properties":{"argv":{"type":"array","items":{"type":"string"}},"cwd":{"type":"string"},"env":{"type":"object","additionalProperties":{"type":"string"}}}}}},
    {"type":"object","required":["driver","shell"], "properties":{"driver":{"const":"shell"}, "shell":{"type":"object","required":["cmd"],"properties":{"cmd":{"type":"string"}}}}},
    {"type":"object","required":["driver","curl"],  "properties":{"driver":{"const":"curl"},  "curl":{"type":"object","required":["method","url"],"properties":{"method":{"type":"string"},"url":{"type":"string"},"headers":{"type":"object","additionalProperties":{"type":"string"}},"body":{}}}}},
    {"type":"object","required":["driver","file"],  "properties":{"driver":{"const":"file"},  "file":{"type":"object","required":["path","mode"],"properties":{"path":{"type":"string"},"mode":{"enum":["read","write"]},"append":{"type":"boolean"},"create_parents":{"type":"boolean"},"allow_outside_project":{"type":"boolean"}}}}},
    {"type":"object","required":["driver","mcp"],   "properties":{"driver":{"const":"mcp"},   "mcp":{"type":"object","required":["server","tool"],"properties":{"server":{"type":"string"},"tool":{"type":"string"},"args":{"type":"object"},"stream":{"type":"boolean"}}}}}
  ]
}
```

---

## CLI authoring examples

```bash
# Exec source
jn new source echo.ndjson --driver exec \
  --argv python -c "import json;print(json.dumps({'x':1}));print(json.dumps({'x':2}))"

# File target
jn new target file.write --driver file --path out/out.ndjson --mode write --create-parents

# Curl GET source
jn new source http.get --driver curl --method GET --url https://httpbin.org/get

# MCP source (sugar → exec argv)
jn new source mcp.search --driver mcp --server github --tool search_repos --arg q=octocat --stream
```

---

## Testing checklist

* **Exec:** prints two JSON lines; `run` pipes through `jq` pass‑through.
* **Shell:** blocked unless `--unsafe-shell`; when allowed, runs simple echo.
* **Curl:** file:// or httpbin.org switchable behind `JN_OFFLINE=1` → use file fixtures.
* **File:** read/write round‑trip including UTF‑16LE with BOM.
* **MCP:** shim stub echoes NDJSON frames; run end‑to‑end.

---

## Non‑functional guardrails (driver‑specific)

* **Binary‑safe:** no `decode()` on hot paths.
* **Backpressure:** pipes connect directly; no internal queues.
* **Limits:** batch fallback bounded by `JN_BUFFER_LIMIT_BYTES`.
* **Secrets:** env printed in `explain` must be redacted unless opted in.

— End Drivers Architecture —

