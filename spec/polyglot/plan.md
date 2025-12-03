# JN Polyglot Implementation Plan

**Status:** In Progress
**Date:** 2024-01 (Updated 2025-12-02)

## Executive Summary

This plan outlines the migration of JN to a polyglot architecture with:
- **ZQ** - Pure Zig jq replacement (v0.4.0, ~4100 lines, Zig 0.15.1+)
- **Zig plugins** - csv, json, jsonl all complete with mode-aware discovery
- **Python CLI** - Orchestration layer with on-demand Zig compilation
- **Python plugins** - gmail, mcp, duckdb, xlsx, and others (complex APIs)
- **Cross-platform builds** - ziglang PyPI package for on-demand compilation

## Sprint Roadmap

| Sprint | Status | Description |
|--------|--------|-------------|
| 01 | ✅ Complete | ZQ foundation: identity, field access, select, pipes |
| 02 | ✅ Complete | Extended: array iteration, slurp mode, arithmetic |
| 03 | ✅ Complete | Aggregation: group_by, sort_by, map, string functions |
| 04 | ✅ Complete | **ZQ jq-compat:** slicing, optional access, has, del, entries |
| 04a | ✅ Complete | **Zig 0.15.2 upgrade:** I/O refactor, build system updates |
| 05 | ✅ Complete | **Error handling + jq removal:** ZQ enhanced, jq_.py deleted |
| 06 | ✅ Complete | **JSONL Zig plugin:** standalone plugin, on-demand build system |
| 06a | ✅ Complete | **Cross-platform builds:** ziglang PyPI, zig_builder.py |
| 07 | ✅ Complete | **CSV & JSON Zig plugins:** mode-aware discovery, registry priority |
| 08 | 🔲 Next | Integration, CI/CD, production release |
| 09 | 🔲 Planned | HTTP & compression Zig plugins |
| 10 | 🔲 Future | **Zig core binary** (replace Python CLI) |

**jq removal:** ✅ Sprint 05 complete - ZQ is now the only filter engine
**Cross-platform:** ✅ Sprint 06a complete - ziglang PyPI package for on-demand compilation
**Zig plugins:** ✅ Sprint 07 complete - CSV, JSON, JSONL all use Zig with Python fallback for write-only modes

## Current State (Sprint 07 Complete)

```
┌─────────────────────────────────────────────────────────────────┐
│                   jn (Python CLI)                               │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌─────────────┐  │
│  │   Click   │  │  Address  │  │  Plugin   │  │   Pipeline  │  │
│  │    CLI    │  │  Parser   │  │ Discovery │  │  Executor   │  │
│  └───────────┘  └───────────┘  └───────────┘  └─────────────┘  │
│                                      │                          │
│                         ┌────────────┴────────────┐             │
│                         ▼                         ▼             │
│              ┌──────────────────┐     ┌──────────────────┐      │
│              │   zig_builder    │     │ Python discovery │      │
│              │ (on-demand build)│     │ (PEP 723 parse)  │      │
│              └──────────────────┘     └──────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   ZQ (Zig)   │      │ Zig Plugins  │      │Python Plugins│
│              │      │              │      │              │
│ • v0.4.0     │      │ • csv ✅     │      │ • gmail      │
│ • 4077 lines │      │ • json ✅    │      │ • mcp        │
│ • 2-3x faster│      │ • jsonl ✅   │      │ • xlsx       │
│ • Zig 0.15.1+│      │              │      │ • yaml, toml │
└──────────────┘      └──────────────┘      └──────────────┘
```

## What's Working

### ZQ Filter Engine (zq/src/main.zig)
- **4077 lines** of Zig (up from ~2600 in plan)
- Version 0.4.0
- Zig 0.15.1+ compatible (comptime version detection for 0.15.1 vs 0.15.2 I/O API)
- Full jq compatibility for JN's use cases

**Supported Features:**
- Identity (`.`), field access (`.foo`, `.foo.bar`)
- Array iteration (`.[]`, `.[n]`, `.[n:m]` slicing)
- Pipes (`|`), select with all comparison operators
- Optional access (`.foo?`, `.[n]?`)
- Slurp mode (`-s`) for aggregations
- Arithmetic (`+`, `-`, `*`, `/`)
- Boolean logic (`and`, `or`, `not`)
- Object construction (`{a: .x, b: .y}`)
- Builtins: `keys`, `values`, `length`, `type`, `empty`, `not`, `null`
- Array functions: `first`, `last`, `reverse`, `sort`, `unique`, `flatten`, `add`, `min`, `max`
- Aggregation: `group_by`, `sort_by`, `unique_by`, `min_by`, `max_by`, `map`
- Object operations: `has`, `del`, `to_entries`, `from_entries`
- String functions: `split`, `join`, `ascii_downcase`, `ascii_upcase`, `startswith`, `endswith`, `contains`, `ltrimstr`, `rtrimstr`
- Math functions: `floor`, `ceil`, `round`, `fabs`, `sqrt`, `log`, `log10`, `exp`, `pow`, `sin`, `cos`, `tan`
- Type conversions: `tonumber`, `tostring`

### On-Demand Build System (src/jn/zig_builder.py)
- **455 lines** of Python
- Uses ziglang PyPI package (>=0.15.1) for cross-platform Zig compiler
- Builds binaries on first use, caches in `~/.local/jn/bin/`
- Source hash-based cache invalidation
- Version-aware Zig command selection (skips incompatible system Zig)
- Bundles Zig sources in wheel for installation

**Build Flow:**
1. Check `$JN_HOME/bin/` for pre-built binary
2. Check development build in repo (`zq/zig-out/bin/zq`)
3. Check PATH for `zq` binary
4. Build from source using ziglang package (cached)

### Plugin Discovery (src/jn/plugins/discovery.py)
- Discovers Python plugins via PEP 723 metadata
- Discovers Zig plugins via `--jn-meta` flag
- On-demand compilation of Zig plugins via `discover_zig_plugins_with_build()`
- Cache-based invalidation for fast subsequent discovery

### Zig Plugins (plugins/zig/)

| Plugin | Lines | Status | Modes | Notes |
|--------|-------|--------|-------|-------|
| jsonl | 188 | ✅ Complete | read, write | Validates JSON, streams NDJSON |
| csv | 523 | ✅ Complete | read, write | Quoted fields, delimiter config |
| json | 279 | ✅ Complete | read only | Array→NDJSON, Python fallback for write |

**Plugin Features:**
- All plugins output `--jn-meta` JSON manifest for discovery
- Zig 0.15.1+ compatible (comptime I/O API selection)
- Mode-aware registry: Zig plugins used when they support the mode, Python fallback otherwise
- Binary plugins get priority over Python plugins with same pattern

---

## Implementation Details

### Cross-Platform Build System

**Dependencies (pyproject.toml):**
```toml
"ziglang>=0.15.1",  # Cross-platform Zig compiler (0.15.1+ required)
```

**Zig Command Resolution (zig_builder.py):**
```python
def get_zig_command() -> list[str]:
    # 1. System zig (if version >= 0.15.1)
    # 2. python-zig from ziglang package (if version >= 0.15.1)
    # 3. python -m ziglang fallback
```

**Binary Caching:**
- Location: `~/.local/jn/bin/`
- Naming: `{name}-{source_hash}` (e.g., `zq-abc123def456`)
- Invalidation: SHA256 hash of source files

### Wheel Packaging

**hatch build config (pyproject.toml):**
```toml
[tool.hatch.build.targets.wheel.force-include]
"zq/src" = "jn_home/zig_src/zq"
"plugins/zig" = "jn_home/zig_src/plugins"
```

This bundles Zig sources in the wheel, enabling on-demand compilation after `pip install`.

### Filter Command Integration (src/jn/cli/commands/filter.py)

```python
def find_zq_binary() -> str | None:
    # 1. $JN_HOME/bin/zq (bundled with jn)
    # 2. zq/zig-out/bin/zq (development build)
    # 3. zq in PATH (system install)
    # 4. Build from source via zig_builder
```

---

## Directory Structure

```
jn/
├── src/jn/                    # Python framework
│   ├── cli/commands/
│   │   └── filter.py         # ZQ integration (find_zq_binary)
│   ├── plugins/
│   │   └── discovery.py      # Plugin discovery (Python + Zig)
│   └── zig_builder.py        # On-demand Zig compilation (455 lines)
│
├── zq/                        # ZQ filter binary
│   ├── src/main.zig          # Main implementation (4077 lines)
│   ├── build.zig             # Zig build configuration
│   └── tests/integration.zig # Integration tests
│
├── plugins/zig/               # Zig plugins (self-contained)
│   ├── jsonl/main.zig        # JSONL plugin (188 lines) ✅
│   ├── csv/main.zig          # CSV plugin (523 lines) ✅
│   └── json/main.zig         # JSON plugin (279 lines) ✅
│
├── jn_home/
│   ├── plugins/              # Python plugins
│   │   ├── formats/          # csv, json, yaml, toml, markdown, table, xlsx
│   │   ├── protocols/        # http, gmail, mcp
│   │   ├── filters/          # (empty - ZQ is binary)
│   │   └── compression/      # gz
│   └── zig_src/              # Bundled in wheel for on-demand build
│       ├── zq/               # ZQ source
│       └── plugins/          # Zig plugin sources
│
└── spec/polyglot/            # Design docs
    ├── plan.md               # This file
    └── sprints/              # Sprint documentation
```

---

## Performance

### ZQ vs jq Benchmarks (500k NDJSON records, 46MB)

| Expression | jq 1.7 | ZQ 0.4.0 | Speedup |
|------------|--------|----------|---------|
| `.` (identity) | 1.99s | 0.67s | **2.95x** |
| `.name` (field) | 1.25s | 0.57s | **2.19x** |
| `.nested.score` | 1.24s | 0.58s | **2.12x** |
| `select(.value > 50000)` | 1.81s | 0.66s | **2.75x** |

### Startup Time

| Component | Time |
|-----------|------|
| Python CLI startup | ~150-200ms |
| ZQ binary startup | <1ms |
| First ZQ build (cached) | ~5-10s |
| Subsequent ZQ calls | <1ms |

---

## Next Steps

### Sprint 08: Integration & CI/CD (Next)
1. GitHub Actions for multi-platform testing
2. Pre-built binaries in releases
3. Performance regression tests
4. Documentation updates

### Sprint 09: HTTP & Compression
1. HTTP plugin using libcurl or Zig std.http
2. Gzip plugin using std.compress.gzip
3. Streaming support for large files

### Sprint 10: Zig Core Binary
1. Replace Python CLI with Zig binary
2. <5ms startup for all commands
3. Keep Python plugins via subprocess

---

## Lessons Learned

### What Worked Well
1. **Pure Zig approach** - No external dependencies, single-file implementation
2. **Comptime version detection** - Handles Zig 0.15.1 vs 0.15.2 API differences
3. **On-demand builds** - ziglang PyPI package enables cross-platform installation
4. **Source hash caching** - Only rebuilds when source changes

### Challenges Overcome
1. **Zig I/O API changes** - "Writergate" in 0.15.2 required comptime branching
2. **Version resolution** - System Zig may be too old; fallback to ziglang package
3. **Binary caching** - Platform-specific names, executable permissions
4. **Mode-aware plugin resolution** - Registry needed to skip Zig plugins that don't support requested mode
5. **Binary plugin invocation** - `run.py` and `cat.py` needed update to invoke binaries directly (not via `uv run`)

### Key Decisions
1. **Self-contained plugins** - No shared Zig library; each plugin is standalone
2. **Python CLI kept** - Complex profile/address resolution stays in Python
3. **ziglang dependency** - Enables `pip install` on any platform with on-demand compilation

---

## References

### Implementation
- `zq/src/main.zig` - ZQ filter implementation (4077 lines)
- `src/jn/zig_builder.py` - On-demand build system (455 lines)
- `src/jn/cli/commands/filter.py` - ZQ integration
- `src/jn/plugins/discovery.py` - Plugin discovery with Zig support
- `plugins/zig/jsonl/main.zig` - Example Zig plugin (188 lines)

### External
- [ziglang PyPI](https://pypi.org/project/ziglang/) - Cross-platform Zig compiler
- [Zig 0.15.1 Release](https://ziglang.org/download/0.15.1/release-notes.html)
- [std.json](https://github.com/ziglang/zig/blob/master/lib/std/json.zig) - Zig JSON parser

### Sprint Documentation
- `spec/polyglot/sprints/01-zq-foundation.md`
- `spec/polyglot/sprints/02-zq-extended.md`
- `spec/polyglot/sprints/03-zq-aggregation.md`
- `spec/polyglot/sprints/04-zq-jq-compat.md`
- `spec/polyglot/sprints/04a-zig-0.15.2-upgrade.md`
- `spec/polyglot/sprints/05-jq-removal.md`
- `spec/polyglot/sprints/06-zig-plugin-library.md`
- `spec/polyglot/sprints/07-zig-csv-json-plugins.md`

---

## Packaging Verification (Sprint 07)

Verified the full packaging and installation workflow:

### Build Process
```bash
uv build
# Creates dist/jn-0.1.0-py3-none-any.whl
# Wheel includes bundled Zig sources in jn_home/zig_src/
```

### Installation via `uv tool install`
```bash
uv tool install --force dist/jn-0.1.0-py3-none-any.whl
# Installs to ~/.local/share/uv/tools/jn/
```

### What's Verified
1. **Wheel packaging** - Zig sources bundled correctly
2. **Tool installation** - `jn` command available system-wide
3. **Plugin discovery** - Both Python and Zig plugins discovered
4. **On-demand Zig compilation** - Zig plugins compile from bundled sources
5. **Mode-aware fallback** - JSON write falls back to Python plugin
6. **Binary caching** - Compiled binaries cached in `~/.local/jn/bin/`

### Test Commands
```bash
# CSV read (Zig) → JSON write (Python)
echo 'name,value\ntest,123' | jn cat /dev/stdin~csv | jn put /dev/stdout~json

# JSON read (Zig) → table display (Python)
echo '[{"a":1},{"a":2}]' | jn cat /dev/stdin~json | jn put /dev/stdout~table

# Full pipeline with filter
jn cat data.csv | jn filter '.revenue > 100' | jn put output.json
```
