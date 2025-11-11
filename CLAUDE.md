# JN Project - Context for Claude

## What is JN?

JN is an **agent-native ETL framework** that uses:
- **Unix processes + pipes** for streaming (not async/await)
- **NDJSON** as the universal data format
- **Standalone Python plugins** for all data operations
- **Automatic backpressure** via OS pipe buffers
- **UV isolation** for dependency management (no virtualenv hell)

Think: `jn cat data.xlsx | jn filter '.revenue > 1000' | jn put output.csv`

---

## Goals

### Functional Goals
**Universal JSON-based ETL that enables AI agents to create on-demand data tools**

JN allows AI agents (like Claude) to:
- **Extract** data from any source (files, APIs, databases, CLIs)
- **Transform** data with filters and transformations
- **Load** data into any destination format
- **Create plugins on-demand** for new data sources/formats
- **Compose pipelines** naturally via Unix pipes

Unlike traditional ETL tools built for humans, JN is optimized for:
- **Agent discoverability** - Regex-based plugin discovery (no imports)
- **Agent extensibility** - Plugins are simple Python scripts with minimal boilerplate
- **Agent composability** - Standard stdin/stdout/NDJSON everywhere
- **Transparent execution** - Subprocess calls are visible and debuggable

### Non-Functional Goals
**High performance with constant memory usage, regardless of data size**

- **Constant memory**: Process 10GB files with ~1MB RAM usage
- **Streaming by default**: First output appears immediately, not after processing entire dataset
- **Parallel execution**: Multi-stage pipelines run concurrently across CPUs
- **Early termination**: `| head -n 10` stops upstream processing after 10 rows
- **No buffering**: Data flows through pipes, never accumulated in memory

### Architectural Approach
**Leverage the OS for concurrency, backpressure, and resource management**

#### 1. **Backpressure via OS Pipes**
- OS pipe buffers (~64KB) automatically block when full
- Slow downstream consumers pause fast upstream producers
- No manual flow control, queues, or async complexity
- See `spec/arch/backpressure.md` for detailed explanation

#### 2. **UV Python Environment Isolation**
- Each plugin declares dependencies via PEP 723 (`# /// script`)
- UV automatically manages isolated environments per plugin
- No virtualenv activation, no dependency conflicts
- First run downloads deps, subsequent runs are instant

#### 3. **Process-based Parallelism**
- Each pipeline stage runs as a separate process
- True parallelism (not Python GIL-limited threads)
- OS scheduler distributes work across CPUs
- SIGPIPE signal propagates shutdown backward through pipeline

#### 4. **Incorporate, Don't Replace**
- Call existing CLIs directly (`jq`, `curl`, `aws`)
- Don't rewrite tools in Python
- Compose battle-tested Unix utilities
- Plugins are thin wrappers when possible

#### 5. **NDJSON as Universal Format**
- Newline-Delimited JSON (one object per line)
- Streamable (unlike JSON arrays)
- Human-readable and tool-friendly
- Universal interchange format between all plugins

---

## Quick Start

```bash
# Install
pip install -e .

# Test
make test    # Run all tests
make check   # Code quality checks

# Use
jn cat data.csv                    # Read CSV → NDJSON
jn cat data.json | jn put out.csv  # JSON → CSV
jn cat data.csv | jn filter '.revenue > 1000' | jn put filtered.json
```

---

## Project Structure

```
jn/
├── src/jn/              # Core framework
│   ├── cli/             # CLI entry and subcommands
│   │   ├── main.py      # CLI entry point
│   │   ├── commands/    # cat, put, filter, head, tail, run
│   │   └── plugins/     # plugin subcommands (list, info, call, test)
│   ├── context.py       # JN_HOME, paths
│   ├── discovery.py     # Plugin discovery (re-export)
│   ├── registry.py      # Pattern matching (re-export)
│   ├── core/            # pipeline + streaming
│   └── plugins/         # plugin system logic (discovery/registry/service)
│
├── jn_home/             # Bundled default plugins (lowest priority)
│   └── plugins/
│       ├── formats/     # csv_.py, json_.py, yaml_.py
│       └── filters/     # jq_.py
│
├── spec/                # Architecture documentation
│   ├── roadmap.md       # Development roadmap
│   └── arch/
│       ├── design.md         # v5 architecture overview
│       ├── backpressure.md   # Why Popen > async
│       └── profiles.md       # Future: API/MCP profiles
│
└── tests/               # Test suite
```

---

## Critical Architecture Decisions

### 1. Use Popen, Not Async

**DO:**
```python
reader = subprocess.Popen([sys.executable, plugin.path, "--mode", "read"],
                         stdin=infile, stdout=subprocess.PIPE)
writer = subprocess.Popen([sys.executable, plugin.path, "--mode", "write"],
                         stdin=reader.stdout, stdout=outfile)
reader.stdout.close()  # CRITICAL for SIGPIPE backpressure!
writer.wait()
reader.wait()
```

**DON'T:**
```python
# NO async/await for data pipelines
# NO subprocess.run(capture_output=True) - buffers everything!
# NO threads - Python GIL kills parallelism
```

**Why:** OS handles concurrency, backpressure, and shutdown automatically. See `spec/arch/backpressure.md`.

### 2. Plugins are Standalone Scripts with PEP 723

**Pattern:**
```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = [".*\\.csv$", ".*\\.tsv$"]
# ///

def reads(config=None):
    """Read CSV from stdin, yield NDJSON records."""
    # ...

def writes(config=None):
    """Read NDJSON from stdin, write CSV to stdout."""
    # ...

if __name__ == '__main__':
    # --mode read|write CLI interface
```

**Key features:**
- UV shebang for direct execution
- PEP 723 TOML for dependencies
- Regex patterns for file matching
- Duck typing (`reads`/`writes` functions)
- Framework passes `--mode` flag

**See:** `jn_home/plugins/formats/csv_.py` for complete example

### 3. NDJSON is the Universal Format

All plugins communicate via NDJSON (one JSON object per line):
```
{"name": "Alice", "age": 30}
{"name": "Bob", "age": 25}
```

**Why:**
- Streamable (unlike JSON arrays)
- Human-readable
- Tool-friendly (`jq`, `grep`)
- Constant memory

---

## Plugin System

### Discovery
1. Scan `$JN_HOME/plugins/` for `.py` files
2. Parse PEP 723 `[tool.jn]` metadata using regex
3. Cache in `cache.json` with timestamp-based invalidation
4. Fallback to built-in plugins if custom dir empty

**See:** `src/jn/discovery.py`

### Pattern Matching
- Plugins declare regex patterns in `[tool.jn] matches = [...]`
- Registry compiles patterns and matches source files
- Longest pattern wins

**See:** `src/jn/registry.py`

### Invocation
```bash
# Framework invokes plugins as subprocesses:
python plugin.py --mode=read < input.csv
python plugin.py --mode=write > output.csv

# Chained:
python csv_.py --mode=read < input.csv | python json_.py --mode=write > output.json
```

---

## Common Patterns

### Two-Stage Pipeline
See `src/jn/core/pipeline.py` (convert) and `src/jn/cli/commands/run.py`:
- Load plugins with fallback
- Resolve input/output plugins via registry
- Start reader and writer as Popen subprocesses
- **Critical:** `reader.stdout.close()` for SIGPIPE
- Wait for both processes

### Filter Pipeline
See `src/jn/cli/commands/filter.py`:
- Find plugin (custom dir → fallback to built-in)
- Run as Popen (inherit stdin/stdout for chaining)
- Wait and check returncode

### Direct Plugin Invocation
```python
# Test plugins directly without framework (bundled defaults)
plugin_path = Path("jn_home/plugins/formats/csv_.py")
result = subprocess.run([sys.executable, str(plugin_path), "--mode", "read"],
                        stdin=f, capture_output=True, text=True)
```

---

## Performance Characteristics

**Memory:** Constant ~1MB regardless of file size (10MB, 1GB, 10GB)

**Early Termination:**
```bash
jn cat https://example.com/1GB.csv | head -n 10
# Downloads ~1KB, processes 10 rows, stops ✅ (not entire 1GB)
```

**Parallel Execution:**
```
CPU1: ████ fetch     CPU2:   ████ parse
CPU3:     ████ filter CPU4:       ████ write
All stages run simultaneously!
```

---

## Architecture Deep Dives

**For implementation details:**
- `spec/arch/design.md` - v5 architecture, PEP 723, duck typing
- `spec/arch/backpressure.md` - Why Popen > async, SIGPIPE, memory
- `spec/roadmap.md` - Development roadmap

**For code examples:**
- `src/jn/cli/commands/run.py` - Pipeline orchestration
- `src/jn/discovery.py` - Plugin discovery (re-export)
- `jn_home/plugins/formats/csv_.py` - Example format plugin
- `jn_home/plugins/filters/jq_.py` - Example filter (wraps jq CLI)

---

## Key Principles

### Unix Philosophy
- Small, focused plugins (each does one thing well)
- stdin → process → stdout (standard interface)
- Compose via pipes (build complex from simple)

### Agent-Friendly
- Plugins are standalone scripts (no framework imports)
- Fast discovery (regex parsing, no execution)
- Self-documenting (PEP 723 metadata)
- Extensible (agents create plugins on-demand)

### Performance
- Streaming by default (constant memory)
- Automatic backpressure (OS handles flow control)
- Parallel execution (multi-CPU via processes)
- Early termination (SIGPIPE propagates shutdown)

### Simplicity
- No async complexity (no async/await)
- No heavy dependencies (click + ruamel.yaml)
- Transparent execution (subprocess calls visible via `ps`)
- UV isolation (no virtualenv hell)

---

## Development

```bash
# Install with dev dependencies
uv sync --all-extras

# Run tests
make test

# Code quality
make check

# See Makefile for more commands
```
