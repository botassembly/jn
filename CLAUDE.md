# JN Project - Context for Claude

## ⚠️ CRITICAL: Always Use JN Commands (Golden Path)

**DO THIS (Correct):**
```bash
jn cat data.csv | jn filter '.x > 10' | jn put output.json
jn cat data.csv --limit 100
jn cat https://api.com/data.json | jn put results.csv
```

**DON'T DO THIS (Wrong - Bypasses Architecture):**
```bash
python jn_home/plugins/formats/csv_.py --mode read < data.csv  # ❌ NO!
python csv_.py --mode read < data.csv | python json_.py --mode write  # ❌ NO!
uv run csv_.py --mode read < data.csv  # ❌ NO!
```

**Why the Golden Path Matters:**
- ✅ Automatic backpressure via OS pipes
- ✅ Memory-efficient streaming (constant memory, any file size)
- ✅ Early termination (`| head -n 10` stops upstream processing)
- ✅ Parallel multi-stage execution across CPUs
- ✅ Better error messages and diagnostics
- ✅ Automatic plugin discovery and format detection

**When writing code or examples, ALWAYS use `jn cat`, `jn put`, `jn filter` - NEVER call plugins directly!**

---

## What is JN?

JN is an **agent-native ETL framework** that uses:
- **Unix processes + pipes** for streaming (not async/await)
- **NDJSON** as the universal data format
- **Standalone Python plugins** for all data operations
- **Automatic backpressure** via OS pipe buffers
- **UV isolation** for dependency management (no virtualenv hell)

Think: `jn cat data.xlsx | jn filter '.revenue > 1000' | jn put output.csv`

---

## Recent Major Additions

**Protocol Support:**
- **HTTP** - Fetch data from REST APIs with profile-based auth
- **MCP** - Model Context Protocol integration for LLM tools
- **Gmail** - Extract messages and threads via Gmail API

**Profile System:**
- Hierarchical API/service configurations
- Credential management without embedding in commands
- Discovery and search: `jn profile list`, `jn profile search`

**Universal Addressing:**
- `address[~format][?params]` syntax for all resources
- Auto-detection of compression (`.gz`) and formats
- Protocol-agnostic plugin resolution

**Plugin Validation:**
- AST-based static analysis (`jn check plugins`)
- Security validation (no eval/exec, approved subprocess patterns)
- Whitelist system for safe code patterns

**Discovery & Introspection:**
- `jn inspect` - Discover API endpoints, MCP resources, data schemas
- `jn analyze` - Analyze NDJSON streams (schema, stats)
- `jn profile discover` - Auto-discover API endpoints

**Shell Integration:**
- `jn sh` - Execute shell commands → NDJSON output
- 70+ commands supported via `jc` (JSON Convert)
- Custom shell plugins for specialized commands

**Additional Formats:**
- XLSX (Excel spreadsheets)
- Markdown (tables and documents)
- TOML (configuration files)
- Table (pretty-printed tables)

**Spec Organization:**
- Reorganized into `done/` (implemented), `wip/` (in progress), `plan/` (planned)
- Clear separation of completed vs. future features
- See `spec/README.md` for navigation

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
- See `spec/done/arch-backpressure.md` for detailed explanation

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

# Basic usage
jn cat data.csv                    # Read CSV → NDJSON
jn cat data.json | jn put out.csv  # JSON → CSV
jn cat data.csv | jn filter '.revenue > 1000' | jn put filtered.json

# Advanced features
jn cat https://api.github.com/users~json | jn head -n 5
jn cat http://myapi/users | jn filter '.active' | jn put out.json
jn inspect http://myapi                # Discover API endpoints
jn profile list                        # List configured profiles
jn sh "ps aux" | jn filter '.cpu > 50' # Shell commands → NDJSON
jn check plugins                       # Validate plugin security
```

---

## Project Structure

```
jn/
├── src/jn/              # Core framework
│   ├── cli/             # CLI entry and subcommands
│   │   ├── main.py      # CLI entry point
│   │   ├── commands/    # cat, put, filter, head, tail, run, analyze, check, inspect, profile, sh
│   │   ├── plugins/     # plugin subcommands (list, info, call, test)
│   │   └── helpers.py   # CLI utilities
│   ├── addressing/      # Universal resource addressing system
│   │   ├── parser.py    # Parse address[~format][?params]
│   │   ├── resolver.py  # Resolve addresses to plugins
│   │   └── types.py     # Address data models
│   ├── checker/         # AST-based plugin validation
│   │   ├── ast_checker.py    # Static analysis engine
│   │   ├── rules/            # Validation rules (forbidden, structure, subprocess)
│   │   ├── scanner.py        # Plugin scanner
│   │   ├── whitelist.py      # Approved pattern whitelist
│   │   ├── violation.py      # Violation models
│   │   └── report.py         # Violation reporting
│   ├── profiles/        # Hierarchical profile system (APIs, MCPs)
│   │   ├── service.py   # Profile discovery and resolution
│   │   ├── resolver.py  # Profile path resolution
│   │   ├── http.py      # HTTP profile handling
│   │   ├── gmail.py     # Gmail profile handling
│   │   └── mcp.py       # MCP profile handling
│   ├── shell/           # Shell command integration
│   │   └── jc_fallback.py   # jc (JSON Convert) integration
│   ├── core/            # Pipeline + streaming
│   │   ├── pipeline.py  # Pipeline orchestration
│   │   ├── streaming.py # Streaming utilities
│   │   └── plugins.py   # Plugin loading
│   ├── plugins/         # Plugin system logic
│   │   ├── discovery.py # Plugin discovery
│   │   ├── registry.py  # Pattern matching
│   │   └── service.py   # Plugin services
│   ├── context.py       # JN_HOME, paths
│   ├── filtering.py     # NDJSON filtering with jq
│   ├── introspection.py # Plugin introspection
│   └── process_utils.py # Process management utilities
│
├── jn_home/             # Bundled default plugins (lowest priority)
│   └── plugins/
│       ├── formats/     # csv_.py, json_.py, yaml_.py, toml_.py, markdown_.py, table_.py, xlsx_.py
│       ├── filters/     # jq_.py
│       ├── protocols/   # http_.py, gmail_.py, mcp_.py
│       ├── compression/ # gz_.py
│       └── shell/       # tail_shell.py, watch_shell.py
│
├── spec/                # Architecture documentation (organized by status)
│   ├── README.md        # Spec organization guide
│   ├── done/            # Fully implemented features
│   │   ├── arch-design.md      # v5 architecture overview
│   │   ├── arch-backpressure.md # Why Popen > async
│   │   ├── addressability.md   # Universal addressing
│   │   ├── plugin-specification.md
│   │   ├── plugin-checker.md
│   │   ├── profile-usage.md
│   │   ├── format-design.md
│   │   ├── http-design.md
│   │   ├── mcp.md
│   │   ├── gmail-profile-architecture.md
│   │   ├── shell-commands.md
│   │   ├── inspect-design.md
│   │   └── work-*.md    # Completed work tickets
│   ├── wip/             # Work in progress
│   │   ├── roadmap.md   # Development roadmap
│   │   └── design-index.md
│   └── plan/            # Planned features
│       ├── profile-cli.md
│       ├── debug-explain-mode.md
│       └── work-*.md    # Planned work tickets
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

**Why:** OS handles concurrency, backpressure, and shutdown automatically. See `spec/done/arch-backpressure.md`.

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

**See:** `src/jn/plugins/discovery.py`

### Pattern Matching
- Plugins declare regex patterns in `[tool.jn] matches = [...]`
- Registry compiles patterns and matches source files
- Longest pattern wins

**See:** `src/jn/plugins/registry.py`

### Invocation
```bash
# Framework invokes plugins as subprocesses:
python plugin.py --mode=read < input.csv
python plugin.py --mode=write > output.csv

# Chained:
python csv_.py --mode=read < input.csv | python json_.py --mode=write > output.json
```

---

## Advanced Features

### Universal Addressing
JN supports a universal addressing syntax for resources:

```
address[~format][?params]
```

**Examples:**
```bash
jn cat data.csv                          # Local file
jn cat https://api.com/data~json         # HTTP with format hint
jn cat https://api.com/data.csv.gz       # Auto-detect compression + format
jn cat "mcp://server/resource?id=123"    # MCP protocol
jn cat "gmail://label/INBOX"             # Gmail messages
```

**How it works:**
1. Parser extracts protocol, path, format hint, and parameters
2. Resolver matches protocol to plugin (http_.py, mcp_.py, etc.)
3. Format hint overrides auto-detection
4. Parameters passed to plugin via query string

**See:** `src/jn/addressing/parser.py`, `spec/done/addressability.md`

### Profile System
Hierarchical configuration for APIs and services:

```
$JN_HOME/profiles/
├── http/
│   └── myapi/
│       ├── _meta.json       # Base URL, auth, headers
│       ├── users.json       # GET /users endpoint
│       └── projects.json    # GET /projects endpoint
├── mcp/
│   └── myserver/
│       └── _meta.json       # MCP server config
└── gmail/
    └── myaccount/
        └── _meta.json       # Gmail credentials
```

**Usage:**
```bash
jn cat http://myapi/users              # Uses profile for auth
jn cat mcp://myserver/resource         # Uses MCP profile
jn filter '.type == "inbox"' --profile gmail://myaccount/filters/inbox
```

**Benefits:**
- Reusable API configurations
- No credentials in commands
- Hierarchical inheritance (_meta.json)
- Discovery via `jn profile list`

**See:** `src/jn/profiles/service.py`, `spec/done/profile-usage.md`

### Plugin Checker
AST-based static analysis for plugin security:

```bash
jn check plugins             # Check all plugins
jn check plugin path.py      # Check specific plugin
```

**Validates:**
- No `eval()`, `exec()`, `compile()`
- No direct `__import__()`
- Subprocess calls use approved patterns
- Required structure (reads/writes functions)
- PEP 723 metadata present

**Whitelist:** `src/jn/checker/whitelist.py` defines approved subprocess patterns

**See:** `src/jn/checker/ast_checker.py`, `spec/done/plugin-checker.md`

### Inspect Command
Unified discovery and analysis:

```bash
jn inspect http://myapi           # Discover API endpoints (from profile)
jn inspect mcp://server           # Discover MCP tools/resources
jn inspect data.csv               # Analyze data structure
jn inspect --container text data  # Analyze as text stream
```

**Modes:**
- **Discovery** - Find available endpoints/resources/tools
- **Analysis** - Examine data structure and schema
- **Container** - Force specific interpretation

**See:** `src/jn/cli/commands/inspect.py`, `spec/done/inspect-design.md`

### Shell Commands
Execute shell commands with JSON output:

```bash
jn sh "ls -la"                    # List files as NDJSON
jn sh "ps aux"                    # Process list as NDJSON
jn sh "df -h"                     # Disk usage as NDJSON
```

**How it works:**
1. Check for custom plugin (e.g., `ls_shell.py`)
2. Fallback to `jc` (JSON Convert) for standard commands
3. Parse output to NDJSON
4. Stream results

**Supported commands** (via jc): ls, ps, df, dig, ping, netstat, env, and 70+ more

**See:** `src/jn/shell/jc_fallback.py`, `spec/done/shell-commands.md`

---

## CLI Commands Reference

### Data Pipeline
- **`jn cat <address>`** - Read data from file/URL/protocol → NDJSON
- **`jn put <address>`** - Write NDJSON from stdin → file/format
- **`jn run <input> <output>`** - Two-stage pipeline (read → write)

### Filtering & Transformation
- **`jn filter <expr>`** - Filter/transform NDJSON using jq expression
- **`jn head [-n N]`** - Output first N records (default 10)
- **`jn tail [-n N]`** - Output last N records (default 10)

### Discovery & Analysis
- **`jn inspect <address>`** - Discover endpoints or analyze data
- **`jn analyze`** - Analyze NDJSON stream (schema, stats)
- **`jn profile list`** - List available profiles
- **`jn profile discover <url>`** - Discover API endpoints
- **`jn profile search <query>`** - Search profiles and endpoints

### Development
- **`jn plugin list`** - List all available plugins
- **`jn plugin info <name>`** - Show plugin details
- **`jn plugin call <name>`** - Invoke plugin directly
- **`jn plugin test [name]`** - Test plugin(s)
- **`jn check plugins`** - Validate all plugins
- **`jn check plugin <path>`** - Validate specific plugin

### Shell Integration
- **`jn sh <command>`** - Execute shell command → NDJSON

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

**Core architecture (spec/done/):**
- `arch-design.md` - v5 architecture, PEP 723, duck typing
- `arch-backpressure.md` - Why Popen > async, SIGPIPE, memory
- `addressability.md` - Universal addressing: `address[~format][?params]`
- `plugin-specification.md` - Plugin development standards
- `plugin-checker.md` - AST-based static analysis

**Advanced features (spec/done/):**
- `profile-usage.md` - Hierarchical profiles for APIs/MCPs
- `inspect-design.md` - Unified discovery and analysis
- `shell-commands.md` - Shell command handling with jc
- `http-design.md` - HTTP protocol plugin
- `mcp.md` - Model Context Protocol integration
- `gmail-profile-architecture.md` - Gmail plugin

**Roadmap (spec/wip/):**
- `roadmap.md` - Development roadmap with status (✅/🚧/🔲)

**Code examples:**
- `src/jn/cli/commands/run.py` - Pipeline orchestration
- `src/jn/plugins/discovery.py` - Plugin discovery
- `src/jn/addressing/parser.py` - Address parsing
- `src/jn/profiles/service.py` - Profile resolution
- `jn_home/plugins/formats/csv_.py` - Example format plugin
- `jn_home/plugins/protocols/http_.py` - Example protocol plugin
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

---

## Documentation Guidelines

**Temporary vs Permanent Documentation:**

- **Permanent docs** → `spec/done/`, `spec/wip/`, `spec/plan/` (organized by status)
- **Temporary analysis/evaluation docs** → Delete after work is done, don't store in `docs/`
- **One-off investigation files** → Delete when no longer needed

Examples:
- `EVALUATION.md` for a specific PR → Delete after merging
- `ANALYSIS.md` for investigating a bug → Delete after fix
- Architecture decisions that inform future work → `spec/done/`

**Rule:** If a doc is only relevant for a single PR/task, delete it. If it has lasting value, put it in `spec/`.
