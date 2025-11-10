# Pipeline Execution

## Overview

JN pipelines chain plugins via Unix pipes. The framework detects file types/URLs, routes to appropriate plugins, and executes them as concurrent processes with automatic backpressure.

## How It Works

**Example:** `jn cat s3://bucket/data.xlsx`

1. **Detection**: URL starts with `s3://`, has `.xlsx` extension
2. **Routing**: Registry finds `s3_get` (transport) + `xlsx_reader` (reader)
3. **Execution**: Spawn processes with Popen, connect via pipes

```
s3_get (fetch) → [pipe] → xlsx_reader (parse) → [pipe] → stdout (NDJSON)
```

## Executor

**Key implementation** (`src/jn/executor.py`):

```python
# Spawn processes
for i, plugin in enumerate(plugins):
    stdin = processes[-1].stdout if i > 0 else None
    proc = subprocess.Popen(plugin_cmd, stdin=stdin, stdout=subprocess.PIPE)
    processes.append(proc)

    # CRITICAL: Close stdout in parent for SIGPIPE
    if i > 0:
        processes[i-1].stdout.close()
```

**Backpressure:** Automatic via OS pipe buffers (see `arch/backpressure.md`)

## Auto-Routing

**Files:**
- Extension-based: `.csv` → `csv_reader`
- Path detection: Finds file locally

**URLs:**
- Scheme detection: `s3://` → `s3_get`, `https://` → `http_get`
- Extension detection: `https://.../file.xlsx` → `http_get` + `xlsx_reader`

**Profiles (future):**
- `@github/repos/...` → HTTP plugin + github profile
- `@github:create_issue` → MCP plugin + github profile

## Memory Usage

**Constant regardless of file size:**
- Each pipe buffer: ~64KB
- Total memory: O(number_of_stages × 64KB)
- 1GB file → ~1MB RAM (not 1GB!)

## Error Handling

- Each stage captures stderr
- Non-zero exit codes reported
- SIGPIPE for early termination (no error)

See also: `arch/backpressure.md` for streaming details
