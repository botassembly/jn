# JN Zig Refactor - Build Context

## Current Phase: Zig Core Migration

Migrating JN from Python to a **pure Zig core** with Python plugin extensibility.

**Documentation:** `spec/` contains the full architecture docs (14 documents).
**Work Log:** `spec/log.md` tracks implementation progress.

---

## Quick Reference

### Makefile Commands

```bash
make install      # Install deps + build Zig components
make test         # Run pytest
make check        # Format, lint, type check, plugin validation
make coverage     # Run tests with coverage report

make zq           # Build ZQ filter engine
make zq-test      # Run ZQ unit + integration tests
make zq-fmt       # Format Zig code

make zig-plugins       # Build Zig plugins
make zig-plugins-test  # Test Zig plugins

make clean        # Remove build artifacts
```

### Zig Build (Direct)

```bash
# ZQ
cd zq && zig build-exe src/main.zig -fllvm -O ReleaseFast -femit-bin=zig-out/bin/zq

# Plugins
cd plugins/zig/jsonl && zig build-exe main.zig -fllvm -O ReleaseFast -femit-bin=bin/jsonl
```

---

## Architecture Overview

```
jn/
├── libs/zig/              # Shared Zig libraries (TO BUILD)
│   ├── jn-core/           # Streaming I/O, JSON, errors
│   ├── jn-cli/            # Argument parsing
│   ├── jn-plugin/         # Plugin interface
│   ├── jn-address/        # Address parsing
│   ├── jn-profile/        # Profile resolution
│   └── jn-discovery/      # Plugin scanning
│
├── tools/zig/             # CLI tools (TO BUILD)
│   ├── jn/                # Orchestrator
│   ├── jn-cat/            # Universal reader
│   ├── jn-put/            # Universal writer
│   ├── jn-filter/         # ZQ wrapper
│   └── ...                # head, tail, join, merge, etc.
│
├── plugins/zig/           # Zig plugins (IN PROGRESS)
│   └── jsonl/             # JSONL passthrough (DONE)
│
├── plugins/python/        # Python plugins (STAY IN PYTHON)
│   ├── xlsx_.py           # Excel (openpyxl)
│   ├── gmail_.py          # Gmail (Google APIs)
│   ├── mcp_.py            # MCP protocol
│   └── duckdb_.py         # DuckDB
│
├── zq/                    # ZQ filter engine (DONE)
│
├── spec/                  # Architecture documentation
│   ├── 00-plan.md         # Implementation phases
│   ├── 01-vision.md       # Philosophy
│   ├── 02-architecture.md # System design
│   └── ...                # 14 total documents
│
├── src/jn/                # Python CLI (legacy, being replaced)
└── jn_home/               # Bundled defaults
```

---

## Implementation Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 0 | Current | Quality foundation - verify tests, demos, baseline |
| 1 | Next | Foundation libraries (libjn-core, libjn-cli, libjn-plugin) |
| 2 | Planned | Plugin refactor - migrate to shared libs |
| 3 | Planned | Address & profile system |
| 4 | Planned | Core CLI tools (jn-cat, jn-put, jn-filter) |
| 5-11 | Planned | Discovery, HTTP, analysis, join/merge, orchestrator |

**Full plan:** `spec/00-plan.md`

---

## Key Design Decisions

### 1. Process + Pipes (Not Async)

```zig
// Spawn pipeline stages as separate processes
// OS handles backpressure via pipe buffers (~64KB)
// SIGPIPE propagates shutdown
```

### 2. NDJSON Universal Format

```
{"name": "Alice", "age": 30}
{"name": "Bob", "age": 25}
```

### 3. Plugin Interface

```bash
# All plugins support:
plugin --mode={read,write,raw,profiles}
plugin --jn-meta  # Output metadata JSON
```

### 4. Priority Order

1. Project plugins (`.jn/plugins/`)
2. User plugins (`~/.local/jn/plugins/`)
3. Bundled plugins (`$JN_HOME/plugins/`)

Within same level: Zig > Python, longer patterns win.

---

## Performance Targets

| Metric | Python | Zig Target |
|--------|--------|------------|
| Startup | 50-100ms | <5ms |
| Memory (10MB) | ~50MB | ~1MB |
| Memory (1GB) | ~500MB+ | ~1MB |

---

## Golden Path (CLI Usage)

```bash
# Always use jn commands, never call plugins directly
jn cat data.csv | jn filter '.x > 10' | jn put output.json
jn cat https://api.com/data~json | jn head -n 5
jn cat @myapi/users?limit=10 | jn put users.csv
```

---

## Quality Gates

```bash
make check   # Must pass before commit
make test    # All tests green
make coverage # ≥70% coverage
```

| Check | Tool | Threshold |
|-------|------|-----------|
| Coverage | coverage.py | ≥70% |
| Lint | ruff | 0 errors |
| Format | black, zig fmt | 0 diffs |
| Plugins | jn check | 0 violations |

---

## Spec Documents

| Doc | Purpose |
|-----|---------|
| `00-plan.md` | Phase-by-phase implementation plan |
| `01-vision.md` | Why JN exists, design principles |
| `02-architecture.md` | Component model, data flow |
| `03-users-guide.md` | CLI usage and workflows |
| `04-project-layout.md` | Repository structure |
| `05-plugin-system.md` | Plugin interface |
| `06-matching-resolution.md` | Address parsing, pattern matching |
| `07-profiles.md` | Hierarchical profiles |
| `08-streaming-backpressure.md` | Why pipes beat async |
| `09-joining-operations.md` | Join and merge |
| `10-python-plugins.md` | PEP 723 plugins |
| `11-demo-migration.md` | Demo inventory |
| `12-testing-strategy.md` | Outside-in testing |
| `13-code-quality.md` | Coverage, linting |

---

## Work Tracking

Progress is tracked in `spec/log.md`.
