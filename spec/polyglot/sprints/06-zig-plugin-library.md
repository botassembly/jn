# Sprint 06: Zig Plugin System

**Status:** ✅ COMPLETE

**Goal:** Create Zig-based plugins with proper integration into JN's discovery system

**Completed:** 2025-12

---

## Summary

Sprint 06 established the Zig plugin system with:
- Self-contained plugin architecture (no shared library dependency)
- Binary plugin discovery via `--jn-meta`
- JSONL plugin as proof of concept (96x faster than Python)
- Full pytest integration tests

### Architectural Decision

**Planned:** Shared `jn-plugin` library in `libs/zig/jn-plugin/`

**Implemented:** Self-contained plugins in `plugins/zig/<name>/`

**Rationale:** Self-contained plugins are simpler to build, deploy, and maintain. Each plugin is a single executable with no dependencies. The shared library approach added complexity without significant benefits for our use case.

---

## Deliverables

### 1. JSONL Plugin (`plugins/zig/jsonl/`)

```
plugins/zig/jsonl/
├── main.zig      # Plugin source (187 lines)
└── bin/
    └── jsonl     # Compiled binary
```

**Features:**
- `--mode=read` - Stream NDJSON passthrough with backpressure
- `--mode=write` - Stream NDJSON passthrough
- `--jn-meta` - Output JSON metadata for discovery

**Performance (100k records):**
| Plugin | Time | Speedup |
|--------|------|---------|
| Python json_.py | 1.637s | baseline |
| Zig jsonl | 0.017s | **96x faster** |

### 2. Binary Plugin Discovery

Updated `src/jn/plugins/discovery.py`:
- Added `discover_binary_plugins()` function
- Added `PluginMetadata.is_binary` field
- Binary plugins override Python plugins with same name

**Discovery flow:**
```
1. Scan plugins/zig/*/bin/ for executables
2. Run binary --jn-meta to get metadata
3. Parse JSON response (name, matches, role)
4. Add to plugin registry with is_binary=True
```

### 3. Makefile Targets

```makefile
zig-plugins      # Build all Zig plugins
zig-plugins-test # Run Zig plugin tests
jsonl-bench      # Performance benchmark
```

### 4. Integration Tests

`tests/plugins/test_zig_jsonl.py` (9 tests):
- `--jn-meta` output validation
- Read mode passthrough
- Write mode passthrough
- Discovery integration

---

## Plugin Protocol

### Metadata (`--jn-meta`)

```json
{
  "name": "jsonl",
  "version": "0.1.0",
  "matches": [".*\\.jsonl$", ".*\\.ndjson$"],
  "role": "format",
  "modes": ["read", "write"]
}
```

### Modes

- `--mode=read` - Read input format, output NDJSON
- `--mode=write` - Read NDJSON, output target format

### I/O Conventions

- Read from stdin, write to stdout
- Errors to stderr
- Line-buffered output for streaming
- 64KB buffers for OS backpressure

---

## Implementation Details

### Zig 0.15.2 I/O API

```zig
// Buffered stdin reader
var stdin_buf: [64 * 1024]u8 = undefined;
var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
const reader = &stdin_wrapper.interface;

// Buffered stdout writer
var stdout_buf: [64 * 1024]u8 = undefined;
var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
const writer = &stdout_wrapper.interface;

// Streaming line-by-line
while (true) {
    const maybe_line = reader.takeDelimiter('\n') catch |err| {
        std.debug.print("error: {}\n", .{err});
        std.process.exit(1);
    };
    if (maybe_line) |line| {
        try writer.writeAll(line);
        try writer.writeByte('\n');
    } else break;
}
try writer.flush();
```

### Build Command

```bash
zig build-exe main.zig -fllvm -O ReleaseFast -femit-bin=bin/jsonl
```

---

## Files Changed

| File | Changes |
|------|---------|
| `plugins/zig/jsonl/main.zig` | New - JSONL plugin |
| `src/jn/plugins/discovery.py` | Added binary plugin discovery |
| `tests/plugins/test_zig_jsonl.py` | New - integration tests |
| `Makefile` | Added zig-plugins targets |

---

## Success Criteria

| Metric | Target | Actual |
|--------|--------|--------|
| Plugin builds | Yes | ✅ |
| --jn-meta output | Valid JSON | ✅ |
| Discovery integration | Works | ✅ |
| Performance vs Python | Faster | ✅ 96x |
| All tests pass | Yes | ✅ 386+9 |

---

## Next Steps

- **Sprint 07:** CSV & JSON Zig plugins
- **Sprint 08:** CI/CD for cross-platform binary distribution
