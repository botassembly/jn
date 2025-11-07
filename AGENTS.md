# Agents & Outside‑In Testing — How We Build JN

## What We're Building

**JN (Junction)** is a streaming pipeline orchestrator that composes `Source → Converter(s) → Target` with NDJSON and jq transforms. It's designed to minimize agent/LLM context usage by turning tools into code on disk.

**Architecture:**
- **Sources** emit bytes via drivers: exec (argv, safe), shell (requires --unsafe-shell), curl (HTTP), file (read), mcp (external tools)
- **Converters** transform streaming JSON/NDJSON via engines: jq (primary), jc (parses CLI output & CSV to JSON), jiter (partial JSON recovery), delimited (CSV/TSV fallback)
- **Targets** consume bytes (same drivers as sources: exec, shell, curl, file, mcp)
- **Pipelines** chain them linearly with OS pipes for O(1) memory, binary-safe streaming

**Key insight about `jc`**: CLI tool that converts output of popular command-line tools (dig, ps, arp, netstat, etc.), file-types (CSV, TSV, etc.), and common strings to JSON. In JN, it's a *converter engine* that turns non-JSON output into JSON/NDJSON before jq transforms.

**Layers** (enforced by Import Linter):
```
CLI (thin, ≤3 imports) → Service (orchestration) → Drivers (I/O adapters)
                      ↘  Config (jn.json loading) → Home (path resolution)
                      ↘  Models (Pydantic, bedrock)
```

## Outside-In Development Process

This is the house style for building **jn**. We always work **outside‑in**:

1. **Write the CLI test first** using Typer’s `CliRunner`.
2. Run it to see the failure.
3. Implement the **smallest possible** slice under the CLI (service/drivers/config/models).
4. Keep it green; commit.
5. Repeat for the next CLI.

---

## Test scaffolding

* **Layout**

  * `tests/` contains only outside‑in tests. No private unit tests for subprocess details.
  * `tests/conftest.py` wires common helpers: a temp project dir, a `jn.json` fixture, sample data, and a `CliRunner`.
* **Fixtures**

  * `jn.json` is created by the tests via `jn init` or direct write.
  * **Data lives in files** under `tests/data/`; pipelines should read/write files via the **file driver** to stay offline.
  * Prefer **exec** (Python one‑liners) for deterministic sources/targets.
* **Tools**

  * Assume `jq` is available. Use `jc` only when testing conversion from CSV/TSV; otherwise prefer the built‑in `delimited` engine in tests.
  * For HTTP, prefer `file://` or local echo servers. If you must, use `https://httpbin.org` sparingly and guard with an env flag.

---

## Minimal test pattern

```python
from typer.testing import CliRunner
from jn.cli import app

runner = CliRunner()

def test_run_echo_pipeline(tmp_path):
    # 1) Arrange: seed project and data
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "jn.json").write_text("""
    {"version":"0.1","name":"demo",
     "sources":[{"name":"echo","driver":"exec","exec":{"argv":["python","-c","import json;print(json.dumps({'x':1}));print(json.dumps({'x':2}))"]}}],
     "converters":[{"name":"pass","engine":"jq","expr":"."}],
     "targets":[{"name":"cat","driver":"exec","exec":{"argv":["python","-c","import sys;print(sys.stdin.read(), end='')"]}}],
     "pipelines":[{"name":"p","steps":[{"type":"source","ref":"echo"},{"type":"converter","ref":"pass"},{"type":"target","ref":"cat"}]}]}
    """)

    # 2) Act: run the CLI
    with runner.isolated_filesystem(temp_dir=tmp_path):
        res = runner.invoke(app, ["run", "p", "--jn", str(tmp_path/"jn.json")])

    # 3) Assert: streaming JSON lines
    assert res.exit_code == 0
    assert res.stdout.count("\n") >= 1
```

> Keep tests tiny, deterministic, and file‑based. No network in CI unless guarded.

---

## CLI module pattern

Each command lives in its own file and is **registered** from `jn.cli.__init__`.

```python
# src/jn/cli/run.py
import typer
from ..config import get_config
from ..service.pipeline import run_pipeline

def register(app: typer.Typer) -> None:
    @app.command()
    def run(pipeline: str, jn: str|None = typer.Option(None, "--jn")) -> None:
        pr = get_config(jn)
        out = run_pipeline(pr, pipeline, {})
        import sys; sys.stdout.buffer.write(out)
```

**Rules:**

* ≤3 imports in CLI modules.
* CLI never touches models or drivers directly (Import Linter enforces this).
* CLI does not log or format payloads; it only writes bytes.

---

## Keep it green

* Add one CLI at a time in this order (see `spec/roadmap.md`).
* After each passing test: commit.
* If a test needs new behavior (e.g., drivers), add a failing test that calls the **user‑visible CLI** first, then implement drivers/service to satisfy it.

---

## Coverage & linting

* `make coverage` must stay ≥70%.
* `make check` runs `black`, `ruff`, type checks, and Import Linter.

---

## Config & fixtures

* `jn.json` is the only project file; tests load it via `--jn` or fixtures.
* Use `${params.*}` interpolation in sample configs to demonstrate parameterization in tests.

---

## Data formats

* Prefer NDJSON for streaming.
* For CSV/TSV, use the `jc` **streaming** parser (`csv-s`) or the minimal `delimited` engine in tests.
* Verify jq filters with golden files when appropriate (`jq --run-tests`).

---

## When network is unavoidable

* Keep to `httpbin.org` and read‑only endpoints.
* Hide tokens/secrets; use `--env KEY=VAL` in tests only when necessary and redact in `explain`.

---

**That’s it:** Outside‑in, CLI‑first, tiny steps, always green.

