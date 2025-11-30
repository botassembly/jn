# Sprint 05: Zig Plugin Library

**Status:** 🔲 PLANNED

**Goal:** Create reusable jn-plugin library for building Zig plugins

**Prerequisite:** Sprint 04 complete (jq removed, ZQ is sole filter)

---

## Deliverables

1. `jn-plugin` Zig library
2. Plugin metadata system (`--jn-meta`)
3. NDJSON utilities
4. Documentation and examples

---

## Phase 1: Library Structure

### Directory Setup
- [ ] Create `libs/zig/jn-plugin/` directory
- [ ] Initialize build.zig
- [ ] Create src/lib.zig

### Core Types
```zig
pub const Plugin = struct {
    name: []const u8,
    version: []const u8,
    matches: []const []const u8,
    role: Role,
    modes: []const Mode,
};

pub const Role = enum { format, filter, protocol };
pub const Mode = enum { read, write, raw };
pub const Config = std.StringHashMap([]const u8);
```

### Quality Gate
- [ ] Library compiles
- [ ] Can import from external project

---

## Phase 2: CLI Framework

### Argument Parsing
- [ ] Parse `--mode=read|write|raw`
- [ ] Parse `--jn-meta` flag
- [ ] Parse key=value options
- [ ] Parse positional arguments

### Plugin Runner
```zig
pub fn run(
    plugin: Plugin,
    handlers: struct {
        reads: ?fn(Config, NdjsonWriter) anyerror!void,
        writes: ?fn(Config, NdjsonReader) anyerror!void,
    },
) !void
```

### Quality Gate
- [ ] `--jn-meta` outputs valid JSON
- [ ] Mode dispatching works
- [ ] Error handling to stderr

---

## Phase 3: NDJSON Utilities

### Writer
```zig
pub const NdjsonWriter = struct {
    buffered: std.io.BufferedWriter,

    pub fn write(self: *@This(), record: anytype) !void;
    pub fn writeJson(self: *@This(), json: []const u8) !void;
    pub fn flush(self: *@This()) !void;
};
```

### Reader
```zig
pub const NdjsonReader = struct {
    buffered: std.io.BufferedReader,
    arena: std.heap.ArenaAllocator,

    pub fn next(self: *@This()) !?std.json.Value;
    pub fn reset(self: *@This()) void;
};
```

### Quality Gate
- [ ] Writer buffers output
- [ ] Reader handles arena resets
- [ ] Both handle large records (>1MB)

---

## Phase 4: JSON Utilities

### Serialization
- [ ] Serialize Zig structs to JSON
- [ ] Serialize std.json.Value
- [ ] Handle nested objects
- [ ] Handle arrays

### Parsing
- [ ] Parse JSON to std.json.Value
- [ ] Parse to typed struct (comptime)
- [ ] Handle malformed JSON gracefully

### Quality Gate
- [ ] Round-trip JSON works
- [ ] Comptime struct parsing works

---

## Phase 5: Metadata System

### Manifest Generation
```zig
pub fn generateManifest(plugin: Plugin) ![]const u8 {
    // Generate JSON manifest
    return
        \\{"name":"csv","version":"0.1.0","matches":[".*\\.csv$"],"role":"format","modes":["read","write"]}
    ;
}
```

### --jn-meta Implementation
- [ ] Output manifest JSON to stdout
- [ ] Exit immediately after
- [ ] Use by discovery system

### Quality Gate
- [ ] `plugin --jn-meta` outputs valid JSON
- [ ] Discovery can parse manifest

---

## Phase 6: Testing

### Unit Tests
- [ ] CLI argument parsing
- [ ] NDJSON reader/writer
- [ ] JSON utilities
- [ ] Manifest generation

### Integration Tests
- [ ] Build example plugin
- [ ] Test read mode
- [ ] Test write mode
- [ ] Test metadata output

### Quality Gate
- [ ] All tests pass
- [ ] Example plugin works end-to-end

---

## Phase 7: Documentation

### API Documentation
- [ ] Document all public functions
- [ ] Document types and enums
- [ ] Usage examples

### Example Plugin
```zig
const std = @import("std");
const jn = @import("jn-plugin");

pub const plugin = jn.Plugin{
    .name = "example",
    .version = "0.1.0",
    .matches = &[_][]const u8{".*\\.example$"},
    .role = .format,
    .modes = &[_]jn.Mode{ .read, .write },
};

pub fn reads(config: jn.Config, writer: *jn.NdjsonWriter) !void {
    // Implementation
}

pub fn writes(config: jn.Config, reader: *jn.NdjsonReader) !void {
    // Implementation
}

pub fn main() !void {
    try jn.run(plugin, .{ .reads = reads, .writes = writes });
}
```

### Quality Gate
- [ ] README with quick start
- [ ] Full API reference
- [ ] Working example

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Library compiles | Yes |
| Example plugin works | Yes |
| --jn-meta output | Valid JSON |
| NDJSON throughput | >100K records/s |
| Documentation | Complete |

---

## Notes

**Design Decisions:**
- Use arena allocator for per-record memory
- Buffered I/O by default
- Comptime plugin metadata (no runtime overhead)
