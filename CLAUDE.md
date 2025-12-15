# JN - Universal Data Pipeline Tool

## Status: Zig Core Migration Complete

JN provides a **pure Zig core** with Python plugin extensibility for data transformation pipelines.

**Documentation:** `spec/` contains the full architecture docs (14 documents).
**Work Log:** `spec/log.md` tracks implementation progress.
**Installation:** See `INSTALL.md` for end-user installation instructions.

---

## Quick Reference

### Makefile Commands

```bash
make bootstrap    # Download latest release for fast development
make build        # Build all Zig components (ZQ, plugins, tools)
make test         # Run all Zig tests
make check        # Validate build with integration tests
make clean        # Remove build artifacts
make fmt          # Format all Zig code

# Individual targets (rarely needed):
make zq                # Build ZQ filter engine
make zig-plugins       # Build Zig plugins
make zig-tools         # Build Zig CLI tools
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
├── libs/zig/              # Shared Zig libraries
│   ├── jn-core/           # Streaming I/O, JSON, errors (DONE)
│   ├── jn-cli/            # Argument parsing (DONE)
│   ├── jn-plugin/         # Plugin interface (DONE)
│   ├── jn-address/        # Address parsing (DONE)
│   ├── jn-profile/        # Profile resolution (DONE)
│   └── jn-discovery/      # Plugin scanning (DONE)
│
├── tools/zig/             # CLI tools (DONE)
│   ├── jn/                # Orchestrator (DONE)
│   ├── jn-cat/            # Universal reader (DONE)
│   ├── jn-put/            # Universal writer (DONE)
│   ├── jn-filter/         # ZQ wrapper (DONE)
│   ├── jn-head/           # Stream head (DONE)
│   ├── jn-tail/           # Stream tail (DONE)
│   ├── jn-analyze/        # NDJSON statistics (DONE)
│   ├── jn-inspect/        # Profile discovery & schema (DONE)
│   ├── jn-join/           # Hash join (DONE)
│   ├── jn-merge/          # Source concatenation (DONE)
│   └── jn-sh/             # Shell command parser (DONE)
│
├── plugins/zig/           # Zig plugins (DONE)
│   ├── csv/               # CSV/TSV parser (DONE)
│   ├── json/              # JSON array ↔ NDJSON (DONE)
│   ├── jsonl/             # NDJSON passthrough (DONE)
│   ├── gz/                # Gzip compression (DONE)
│   ├── yaml/              # YAML parser (DONE)
│   ├── toml/              # TOML parser (DONE)
│   └── opendal/           # Protocol handler (EXPERIMENTAL)
│
├── zq/                    # ZQ filter engine (DONE)
│
├── jn_home/               # Bundled defaults
│   └── plugins/           # Python plugins (PEP 723 standalone)
│       ├── xlsx_.py       # Excel (openpyxl)
│       ├── gmail_.py      # Gmail (Google APIs)
│       ├── mcp_.py        # MCP protocol
│       ├── duckdb_.py     # DuckDB
│       └── ...            # Plus xml_, lcov_, markdown_, etc.
│
├── spec/                  # Architecture documentation
│   ├── 00-plan.md         # Implementation phases
│   ├── 01-vision.md       # Philosophy
│   ├── 02-architecture.md # System design
│   └── ...                # 14 total documents
│
└── tests/                 # Python integration tests
```

---

## Implementation Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 0 | ✅ Done | Quality foundation - verify tests, demos, baseline |
| 1 | ✅ Done | Foundation libraries (jn-core, jn-cli, jn-plugin, jn-address, jn-profile) |
| 2 | ✅ Done | Plugin refactor - CSV/JSON/JSONL/GZ use shared libs |
| 3 | ⚠️ Partial | OpenDAL protocol plugin (HTTP works, S3 needs testing) |
| 4 | ✅ Done | Address & profile system |
| 5 | ✅ Done | Core CLI tools (jn-cat, jn-put, jn-filter, jn-head, jn-tail) |
| 6 | ✅ Done | Plugin discovery library |
| 7 | ✅ Done | Analysis tools (jn-analyze, jn-inspect) |
| 8 | ✅ Done | Join & Merge (jn-join, jn-merge, jn-sh) |
| 9 | ✅ Done | Orchestrator (jn command) |
| 10 | ✅ Done | Extended formats (YAML, TOML plugins) |
| 11 | ✅ Done | Testing & migration (integration tests, benchmarks) |

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

## Performance Results

Benchmarked on 5,000 NDJSON records:

| Metric | Python CLI | Zig Tools | Improvement |
|--------|------------|-----------|-------------|
| Startup | ~2000ms | ~1.5ms | **1300x faster** |
| Head (100 records) | ~1800ms | ~2ms | **900x faster** |
| Tail (100 records) | ~2000ms | ~4ms | **500x faster** |
| Throughput | ~2,700 rec/s | ~3M rec/s | **1100x faster** |

*Benchmarks measured before Python CLI removal.*

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
make test    # All tests green
make fmt     # Format Zig code
```

| Check | Tool | Threshold |
|-------|------|-----------|
| Tests | Zig test runner | All pass |
| Format | zig fmt | 0 diffs |

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

## Agent Bootstrapping Guide

When starting work on this codebase, use the release build to speed up development.

### Quick Start for Agents

```bash
# Option 1: Use the bootstrap script (recommended)
make bootstrap
export JN_HOME="/tmp/jn-release"
export PATH="$JN_HOME/bin:$PATH"

# Option 2: Manual download
curl -LO https://github.com/botassembly/jn/releases/latest/download/jn-linux-x86_64.tar.gz
mkdir -p /tmp/jn-release
tar -xzf jn-linux-x86_64.tar.gz -C /tmp/jn-release --strip-components=1
export JN_HOME="/tmp/jn-release"
export PATH="$JN_HOME/bin:$PATH"

# Verify it works
jn --version
echo '{"test":1}' | jn filter '.'
```

### Why Use the Release Build?

Building from source takes 2-3 minutes and rebuilds 20+ tools. Using release binaries:

- **Instant testing**: Test changes without rebuilding everything
- **Plugin availability**: All plugins (csv, json, yaml, etc.) are pre-built
- **Tool discovery works**: Tools find each other via `$JN_HOME/bin/`

### Development Workflow

**When modifying a single tool:**

```bash
# Use release for all dependencies
export JN_HOME="/tmp/jn-release"
export PATH="$JN_HOME/bin:$PATH"

# Rebuild only the tool you're changing
cd tools/zig/jn-cat
zig build-exe -fllvm -O ReleaseFast \
  --dep jn-core --dep jn-cli --dep jn-address --dep jn-profile \
  -Mroot=main.zig \
  -Mjn-core=../../../libs/zig/jn-core/src/root.zig \
  -Mjn-cli=../../../libs/zig/jn-cli/src/root.zig \
  -Mjn-address=../../../libs/zig/jn-address/src/root.zig \
  -Mjn-profile=../../../libs/zig/jn-profile/src/root.zig \
  -femit-bin=bin/jn-cat

# Test immediately - uses release plugins
./bin/jn-cat test.csv
```

**When doing full validation:**

```bash
# Run full build and test
make test

# Run integration checks
make check
```

### Validating Your Changes

Always run these before committing:

```bash
make test      # Unit tests for all components
make check     # Integration tests with real data
make fmt       # Format code (run if fmt fails in CI)
```

### Release Build Layout

The release uses a flat `bin/` directory:

```
$JN_HOME/
├── bin/
│   ├── jn, jn-cat, jn-put, ...  # All tools
│   ├── csv, json, yaml, ...     # All plugins
│   └── zq                        # Filter engine
└── jn_home/
    └── plugins/                  # Python plugins only
```

Tools discover plugins/tools in this order:
1. `$JN_HOME/bin/{name}` (release layout)
2. Sibling executables (same directory)
3. `plugins/zig/{name}/bin/{name}` (development layout)
4. `~/.local/jn/bin/{name}` (user install)

### CLI Argument Notes

Short options require `=` syntax:
- `jn head --lines=5` works
- `jn head -n=5` works
- `jn head -n 5` does NOT work (space-separated)

---

## Creating Releases

Releases are created via git tags and built by GitHub Actions.

### Release Process

```bash
# 1. Ensure all changes are committed and pushed
git status  # Should be clean

# 2. Create and push a version tag
git tag v0.1.0
git push origin v0.1.0
```

### What Happens on Tag Push

1. **Build job runs automatically** - compiles all tools with version from tag
2. **Release job waits for approval** - requires "release" environment approval in GitHub
3. **After approval** - publishes to GitHub Releases with:
   - `jn-{VERSION}-x86_64-linux.tar.gz` (versioned)
   - `jn-linux-x86_64.tar.gz` (consistent "latest" filename)

### Version Embedding

CI extracts version from the git tag and writes to `tools/zig/jn/version.txt` before building. The `jn` binary embeds this at compile time via `@embedFile("version.txt")`.

Local development uses `version.txt` which defaults to `0.0.0`.

### Prerelease Tags

Tags containing `-alpha`, `-beta`, or `-rc` are marked as prereleases:
- `v1.0.0-alpha` → prerelease
- `v1.0.0-rc1` → prerelease
- `v1.0.0` → full release

### Security

The release job requires approval from the "release" environment. Configure reviewers in:
Settings → Environments → release → Required reviewers

This prevents unauthorized releases even if someone has push access.

---

## Work Tracking

Progress is tracked in `spec/log.md`.
