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

| Sprint | Focus | Status |
|--------|-------|--------|
| [01-foundation-csv-plugin](sprints/01-foundation-csv-plugin.md) | Zig build, CSV plugin | Planned |

---

## Implementation Roadmap

### Phase 1: ZQ Filter Language

Build ZQ as the first Zig component to validate the toolchain and architecture.

**Why ZQ first?**
- Isolated component (no core changes needed)
- Clear success criteria (benchmark vs jq)
- Proves Zig JSON handling at scale
- Immediate value (faster filters)

**Deliverables:**
1. ZQ binary with core expressions (see [ZQ.md](ZQ.md))
2. Integration with `jn filter` command
3. Benchmark suite

### Phase 2: Zig Core Infrastructure

Migrate jn binary from Python to Zig.

**Components:**
- CLI argument parsing
- Address parsing (`address[~format][?params]`)
- Plugin discovery and manifest loading
- Pipeline orchestration (Popen equivalent)

### Phase 3: Format Plugins

Migrate hot-path format plugins to Zig.

**Priority order:**
1. JSON/JSONL (most common)
2. CSV (complex, validates parser design)
3. YAML/TOML (simpler)
4. GZ (compression wrapper)

### Phase 4: Protocol Plugins

Migrate HTTP plugin to Zig (optional, Python works fine for protocols).

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
