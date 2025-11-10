# JN Project - Context for Claude

## Critical Architecture Decisions

### Process-Based Streaming with Backpressure

**DO NOT suggest async/await or asyncio for data pipelines.**

JN uses **Unix processes + pipes** for streaming, which is:
- ✅ Superior to async I/O for pipelines
- ✅ Automatic backpressure via OS pipes
- ✅ True parallelism (multi-CPU)
- ✅ Simpler (no async syntax)
- ✅ More robust (isolated memory)

**Key implementation:**
```python
# ALWAYS use Popen, NEVER subprocess.run(capture_output=True)
process = subprocess.Popen(cmd, stdin=stdin, stdout=subprocess.PIPE)

# CRITICAL: Close stdout in parent for SIGPIPE propagation
prev_process.stdout.close()
```

See `spec/popen-backpressure.md` for details.

---

## Plugin System

**Plugins are standalone Python scripts** that:
- Read from `stdin` (binary or text)
- Write to `stdout` (NDJSON or binary)
- Declare dependencies via PEP 723 inline metadata
- Are discovered via regex (no imports needed)

**Plugin categories:**
- **Transport** (sources): Fetch bytes from URLs → stdout
- **Readers** (sources): Parse formats → NDJSON
- **Filters** (transforms): NDJSON → NDJSON
- **Writers** (targets): NDJSON → format

**Framework orchestrates, plugins execute.**

---

## Streaming Guidelines

### DO Stream:
- Transport plugins (s3_get, ftp_get): Use Popen + 64KB chunks
- Filter plugins (jq_filter): Use Popen stdin → stdout
- Readers: Yield records incrementally from stdin

### MUST Buffer (Format Constraints):
- Writers (csv_writer, json_writer, xlsx_writer): Need all data for headers/wrapping
- XLSX reader: ZIP format requires full file before parsing

### Pattern for Streaming:
```python
# Good: Popen with pipes
process = subprocess.Popen(['tool'], stdin=sys.stdin, stdout=subprocess.PIPE)
for line in process.stdout:
    yield process_line(line)

# Bad: subprocess.run with buffering
result = subprocess.run(['tool'], capture_output=True)  # ← Buffers entire output!
```

---

## Code Organization

```
src/jn/          - Core framework (orchestration)
  ├─ discovery.py  - Plugin discovery (regex-based)
  ├─ registry.py   - Extension → plugin mapping
  ├─ pipeline.py   - Pipeline building
  ├─ executor.py   - Popen + pipes execution
  └─ cli.py        - CLI commands

plugins/         - Domain logic (standalone scripts)
  ├─ readers/      - Format parsers
  ├─ writers/      - Format generators
  ├─ filters/      - NDJSON transformations
  ├─ http/         - Transport plugins
  └─ shell/        - Shell command wrappers

spec/            - Architecture docs
docs/            - User documentation
```

---

## Testing Philosophy

**Outside-in testing with real data:**
- Use real public URLs (no mocks)
- Test with actual files
- Validate end-to-end pipelines

Each plugin has:
- `examples()` - Test cases with real data
- `test()` - Outside-in tests (not unit tests)

---

## Dependencies

**Minimize Python dependencies:**
- Use subprocess for external tools (curl, aws, jq)
- PEP 723 inline metadata for plugin-specific deps
- Framework has minimal deps (only click for CLI)

**Why subprocess over libraries:**
- No heavy deps (boto3 is ~50MB)
- Users' existing config works (AWS profiles, etc.)
- Simple, debuggable, transparent

---

## Current State (2024)

**Latest work:**
- ✅ XLSX multi-transport support (HTTP, S3, FTP)
- ✅ Streaming with backpressure (Popen + pipes)
- ✅ Automatic pipeline routing (jn cat URL detects extension)
- ✅ Transport plugins use 64KB chunked streaming
- ✅ jq_filter updated to use Popen streaming

**Architecture audit:** EXCELLENT
- Framework properly uses Popen
- Backpressure works automatically
- Plugin separation is clean

---

## Common Pitfalls to Avoid

### ❌ Don't: Buffer with subprocess.run
```python
result = subprocess.run(cmd, capture_output=True)  # Buffers all output!
data = result.stdout  # Entire file in memory
```

### ✅ Do: Stream with Popen
```python
process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
for chunk in process.stdout:
    handle_chunk(chunk)  # Process incrementally
```

### ❌ Don't: Suggest async/await for pipelines
Processes + pipes are simpler and better for data pipelines.

### ✅ Do: Use Popen + pipes
OS handles concurrency, backpressure, and shutdown automatically.

### ❌ Don't: Add heavy Python dependencies
Use subprocess to call external tools instead.

### ✅ Do: Keep framework lean
Plugins can have deps (PEP 723), but core should be minimal.

---

## Key Files to Reference

### Architecture & Design
- `spec/ARCHITECTURE.md` - **START HERE** - Full system architecture, plugin patterns, data flow
- `spec/popen-backpressure.md` - **CRITICAL** - Why Popen > async, memory usage, SIGPIPE
- `spec/ROADMAP.md` - Feature roadmap, v4.2.0 targets MCP + Cloud APIs
- `spec/API_MCP_DESIGN.md` - **NEW** - API/MCP integration and profile system (v4.2.0)
- `spec/IMPLEMENTATION_PLAN.md` - Implementation details and patterns

### Reference Implementations
- `src/jn/executor.py` - Pipeline execution (Popen + pipes reference)
- `src/jn/discovery.py` - Regex-based plugin discovery
- `src/jn/registry.py` - Extension/URL to plugin mapping

### Example Plugins (Study These!)
- `plugins/http/s3_get.py` - **Streaming transport** (64KB chunks, Popen)
- `plugins/http/http_get.py` - **REST API source** (GET, JSON handling)
- `plugins/filters/jq_filter.py` - **Streaming filter** (Popen stdin→stdout)
- `plugins/readers/csv_reader.py` - **Incremental reader** (yield per row)
- `plugins/writers/csv_writer.py` - **Buffering writer** (collect all, then write)

---

## Philosophy

**Unix Philosophy:**
- Small, focused plugins
- stdin → process → stdout
- Compose via pipes
- Do one thing well

**Agent-Friendly:**
- Plugins are standalone scripts (no imports)
- Regex-based discovery (fast, no execution)
- Self-contained (PEP 723 deps)
- Transparent (can read source easily)

**Performance:**
- Streaming by default
- Automatic backpressure
- Parallel execution via processes
- Low memory usage

---

## When Working on JN

1. **Check plugin type** - Is it source/filter/target?
2. **Use Popen for streaming** - Not subprocess.run
3. **Close stdout in parent** - For SIGPIPE propagation
4. **Test with real data** - Outside-in, not mocked
5. **Keep it simple** - Unix pipes handle complexity
6. **Document backpressure** - It's automatic, explain why

---

## API & MCP Strategy (v4.2.0 Roadmap)

### Two Core Plugins: HTTP and MCP

**HTTP Plugin** (`plugins/http/http.py`)
- Handles REST API requests (GET, POST, PUT, PATCH, DELETE)
- Path-based resources: `@github/repos/org/repo/issues`
- Profile-driven: base_url, headers, auth, timeout, retry

**MCP Plugin** (`plugins/mcp/mcp.py`)
- Handles MCP server communication
- Tool-based resources: `@github:create_issue`
- Profile-driven: server command, env vars, timeout

**No special commands** - `jn cat` and `jn put` work with both via auto-discovery.

### Profile System

**Structure:**
```
~/.local/jn/profiles/      # User home (not ~/.jn to avoid pollution)
  ├─ http/
  │  ├─ github.json        # Simple: single file
  │  └─ stripe/            # Complex: nested with overrides
  │     ├─ config.json     # Base config
  │     └─ charges.json    # Override for /charges endpoint
  └─ mcp/
     ├─ github.json
     └─ context7/
        ├─ config.json
        └─ search.json     # Override for search tool
```

**JN_HOME Priority (highest to lowest):**
1. `--home <path>` (CLI flag)
2. `$JN_HOME` (environment variable)
3. `./.jn` (current working directory - project-specific)
4. `~/.local/jn` (user home - default)

**Usage:**
```bash
# HTTP (path-based)
jn cat @github/repos/anthropics/claude-code/issues
jn put @stripe/customers < data.ndjson

# MCP (tool-based, note the colon)
jn cat @github:get_issues < args.ndjson
jn put @context7:ingest < docs.ndjson

# Explicit plugin (when profile exists in multiple)
jn cat @http/github/repos/...    # Force HTTP
jn cat @mcp/github:get_issues    # Force MCP
```

### Auto-Discovery

**Syntax-based routing:**
- `/` after profile → HTTP plugin (path-based)
- `:` after profile → MCP plugin (tool-based)

**Profile discovery:**
- Searches `profiles/*/name.json` across all JN_HOME locations
- Alphabetical priority if multiple plugins have same profile name
- Warns user, suggests explicit syntax

### Plugin-Owned Profiles

Each plugin:
- Defines its profile schema
- Validates profiles (optional)
- Provides templates for `jn profile create`
- Returns schemas for sources/targets (optional)

Framework just loads and routes - **plugins own their config.**

### Key Design Principles

✅ **Simple by default** - Single file profiles for basic cases
✅ **Powerful when needed** - Nested profiles for per-resource overrides
✅ **Auto-discovery** - No special commands, syntax hints routing
✅ **Cascading homes** - Project overrides user, explicit overrides all
✅ **Duck typing** - Plugins implement capabilities optionally

See `spec/API_MCP_DESIGN.md` for complete design details.

---

## Version Info

- Current: v4.0.0-alpha1
- Branch: claude/api-plugin-strategy-011CUyR9Mx1yrXG8iBDnUKLK
- Roadmap: v4.2.0 targets MCP + Cloud APIs (Week +14)
- See `spec/ROADMAP.md` for full timeline
