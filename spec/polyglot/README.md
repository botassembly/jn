# Polyglot Plugin Architecture

JN is migrating to a polyglot architecture: **Zig core, Zig plugins, Python for complex APIs**.

## Why Zig?

| Metric | Python | Zig |
|--------|--------|-----|
| Startup time | 150-200ms | <5ms |
| CSV 1GB throughput | 20s | 2s |
| Binary size | N/A | <500KB |
| Cross-compile | Complex | Single command |
| Dependencies | pip/venv | Zero runtime |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     jn (Zig binary)                         │
│  CLI parsing │ Address parsing │ Discovery │ Pipeline exec  │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ Zig Plugins │   │     ZQ      │   │Python Plugs │
│ csv, json   │   │  (filter)   │   │ gmail, mcp  │
│ http, gz    │   │             │   │ duckdb,xlsx │
└─────────────┘   └─────────────┘   └─────────────┘
```

## Plugin Assignment

| Zig (hot path) | ZQ (filter) | Python (complex APIs) |
|----------------|-------------|----------------------|
| csv, json, jsonl | select, field access | gmail, mcp |
| gz, http | object construction | duckdb, xlsx |
| yaml, toml | aggregation | markdown, table |

---

## Documentation Index

### Design Documents

| Document | Description |
|----------|-------------|
| [ZQ.md](ZQ.md) | ZQ filter language specification |
| [plan.md](plan.md) | Detailed implementation plan |

### Experiments (Validated)

| Experiment | Result | Key Finding |
|------------|--------|-------------|
| [zig-cimport](experiments/zig-cimport/) | PASS | @cImport with PCRE2 works |
| [zig-stream-bench](experiments/zig-stream-bench/) | PASS | 35x faster than Python |
| [zig-cross-compile](experiments/zig-cross-compile/) | PASS | All 5 platforms build |
| [zig-jq-subset](experiments/zig-jq-subset/) | PASS | 2-3x faster than jq |

See [experiments/RESULTS.md](experiments/RESULTS.md) for detailed benchmark data.

### Sprint Plans

| Sprint | Focus | Deliverables |
|--------|-------|--------------|
| [01-zq-foundation](sprints/01-zq-foundation.md) | ZQ core features | Identity, field access, select, boolean logic |
| [02-zq-extended](sprints/02-zq-extended.md) | ZQ extended | Object construction, pipes, conditionals |
| [03-zq-aggregation](sprints/03-zq-aggregation.md) | ZQ aggregation | Arrays, slurp mode, group_by, map |
| [04-zig-plugin-library](sprints/04-zig-plugin-library.md) | jn-plugin library | Reusable library for Zig plugins |
| [05-csv-json-plugins](sprints/05-csv-json-plugins.md) | Format plugins | CSV and JSON plugins using library |
| [06-integration](sprints/06-integration.md) | Production ready | CI, testing, benchmarks, release |

---

## Implementation Roadmap

### Sprints 01-03: ZQ Filter Language

Build ZQ as the first Zig component to validate the toolchain and architecture.

**Why ZQ first?**
- Isolated component (no core changes needed)
- Clear success criteria (benchmark vs jq)
- Proves Zig JSON handling at scale
- Immediate value (faster filters)

**Progression:**
1. **Sprint 01:** Core expressions (`.field`, `select`, boolean logic)
2. **Sprint 02:** Object construction, pipes, conditionals
3. **Sprint 03:** Arrays, aggregation, full ZQ.md spec

### Sprint 04: Zig Plugin Library

Create reusable `jn-plugin` library for building Zig plugins.

**Components:**
- CLI argument parsing (`--mode`, `--jn-meta`)
- NDJSON reader/writer with buffering
- Manifest generation

### Sprint 05: Format Plugins

Build production CSV and JSON plugins.

**Plugins:**
- CSV (read/write) - most common format
- JSON (read) - array → NDJSON
- JSONL (read/write) - validation pass-through

### Sprint 06: Integration & Production

Full testing, CI/CD, and release process.

**Deliverables:**
- Cross-platform CI (5 targets)
- Performance regression suite
- Documentation
- Release artifacts

---

## Validated Assumptions

From [experiments/RESULTS.md](experiments/RESULTS.md):

| Assumption | Experiment | Result |
|------------|------------|--------|
| C library interop works | zig-cimport | PASS - PCRE2 via @cImport |
| 10x faster than Python | zig-stream-bench | PASS - 35x faster |
| Cross-compile all platforms | zig-cross-compile | PASS - 5 targets |
| Can beat jq performance | zig-jq-subset | PASS - 2-3x faster |

## Key Learnings

### Zig 0.11.0 Gotchas

```zig
// Use this for source files (not b.path())
.root_source_file = .{ .path = "src/main.zig" },

// Use @import("builtin") not std.Target.current
const builtin = @import("builtin");
```

### Arena Allocator Pattern

Critical for NDJSON processing - reset per line, not per allocation:

```zig
var arena = std.heap.ArenaAllocator.init(page_alloc);
while (readLine()) |line| {
    _ = arena.reset(.retain_capacity);  // O(1) reset
    // process line...
}
```

### Performance Hierarchy

1. **ArenaAllocator** - Use for per-record processing
2. **Buffered I/O** - Always buffer both stdin and stdout
3. **Direct evaluation** - Avoid AST interpretation when possible
4. **Single parse** - Don't convert JSON → intermediate → JSON

---

## CLI Contract

All plugins (Zig or Python) implement:

```
plugin --mode=read|write [OPTIONS]
  stdin:  bytes (read) or NDJSON (write)
  stdout: NDJSON (read) or bytes (write)
  --jn-meta: output plugin metadata as JSON
```

## Manifest Format

```json
{
  "name": "csv",
  "matches": [".*\\.csv$"],
  "role": "format",
  "modes": ["read", "write"]
}
```

Binary plugins auto-generate manifest via `--jn-meta`.

---

## Getting Started

### Run Experiments

```bash
cd spec/polyglot/experiments

# ZQ prototype
cd zig-jq-subset
zig build -Doptimize=ReleaseFast
echo '{"x":1}' | ./zig-out/bin/zq '.x'

# Stream benchmark
cd ../zig-stream-bench
zig build -Doptimize=ReleaseFast
# Generate test data and compare to Python

# Cross-compile test
cd ../zig-cross-compile
./build-all.sh
```

### Build ZQ

```bash
cd spec/polyglot/experiments/zig-jq-subset
zig build -Doptimize=ReleaseFast
zig build test
```

---

## Next Steps

1. **Complete ZQ Phase 1** - Core expressions per [ZQ.md](ZQ.md)
2. **Integrate with JN** - Replace jq calls with ZQ binary
3. **Benchmark suite** - Automated performance regression tests
4. **Begin Zig core** - CLI parsing, plugin discovery
