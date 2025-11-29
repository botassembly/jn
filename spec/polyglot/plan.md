# JN Polyglot Implementation Plan

**Status:** Final Plan
**Date:** 2024-01

## Executive Summary

This plan outlines the migration of JN to a polyglot architecture with:
- **Zig core** - CLI, address parsing, pipeline execution
- **Zig plugins** - csv, json, jsonl, http (hot path)
- **Rust plugin** - jq replacement (jaq-based filter)
- **Python plugins** - gmail, mcp, duckdb, and others (complex APIs)
- **Core libraries** - Python, Zig, Rust for plugin development

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     jn (Zig binary)                             │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌─────────────┐  │
│  │    CLI    │  │  Address  │  │  Plugin   │  │  Pipeline   │  │
│  │  Parser   │  │  Parser   │  │ Discovery │  │  Executor   │  │
│  └───────────┘  └───────────┘  └───────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ Zig Plugins  │      │ Rust Plugin  │      │Python Plugins│
│              │      │              │      │              │
│ • csv        │      │ • jq (jaq)   │      │ • gmail      │
│ • json       │      │              │      │ • mcp        │
│ • jsonl      │      │              │      │ • duckdb     │
│ • http       │      │              │      │ • xlsx       │
│ • gz         │      │              │      │ • markdown   │
│ • yaml       │      │              │      │ • table      │
│ • toml       │      │              │      │ • xml        │
└──────────────┘      └──────────────┘      └──────────────┘
```

---

## Phase 1: Foundation (Week 1-2)

### 1.1 Core Libraries

Create plugin development libraries for all three languages.

#### Python Core Library (`jn_plugin`)

Location: `libs/python/jn_plugin/`

```python
from jn_plugin import Plugin, ndjson

plugin = Plugin(
    name="example",
    matches=[r".*\.example$"],
    role="format",
)

@plugin.reader
def reads(config=None):
    for line in sys.stdin:
        yield {"data": line.strip()}

@plugin.writer
def writes(config=None):
    for record in ndjson.read_stdin():
        print(format_output(record))

if __name__ == "__main__":
    plugin.run()
```

#### Zig Core Library (`jn-plugin-zig`)

Location: `libs/zig/jn-plugin/`

```zig
const jn = @import("jn-plugin");

pub const plugin = jn.Plugin{
    .name = "csv",
    .matches = &[_][]const u8{ ".*\\.csv$", ".*\\.tsv$" },
    .role = .format,
};

pub fn reads(config: jn.Config, writer: jn.NdjsonWriter) !void {
    var reader = jn.stdinReader();
    while (try reader.next()) |line| {
        try writer.write(.{ .data = line });
    }
}

pub fn writes(config: jn.Config, reader: jn.NdjsonReader) !void {
    while (try reader.next()) |record| {
        try std.io.getStdOut().writer().print("{s}\n", .{record.data});
    }
}

pub fn main() !void {
    try jn.run(plugin, .{ .reads = reads, .writes = writes });
}
```

#### Rust Core Library (`jn-plugin-rs`)

Location: `libs/rust/jn-plugin/`

```rust
use jn_plugin::{Plugin, Config, NdjsonWriter, run};
use serde::{Deserialize, Serialize};

#[derive(Plugin)]
#[plugin(name = "jq", role = "filter")]
struct JqPlugin;

impl JqPlugin {
    fn filters(&self, config: Config, writer: &mut NdjsonWriter) -> Result<()> {
        let expr = config.get("expr")?;
        for record in jn_plugin::stdin_ndjson() {
            let result = jaq_core::run(&expr, record)?;
            writer.write(&result)?;
        }
        Ok(())
    }
}

fn main() {
    run::<JqPlugin>();
}
```

### 1.2 First Zig Plugin: CSV

Start with CSV as it's:
- Simple, well-defined format
- High-impact (most common format)
- Good test of the full pipeline

**Dependencies:**
- [zig_csv](https://github.com/matthewtolman/zig_csv) - SIMD-accelerated CSV parser
- Or use [simdjson](https://github.com/simdjson/simdjson) via `@cImport` for JSON output

**Implementation:**

```zig
// plugins/zig/csv/src/main.zig
const std = @import("std");
const jn = @import("jn-plugin");
const csv = @import("zig-csv");

pub const plugin = jn.Plugin{
    .name = "csv",
    .version = "0.1.0",
    .matches = &[_][]const u8{ ".*\\.csv$", ".*\\.tsv$" },
    .role = .format,
};

pub fn reads(config: jn.Config, writer: anytype) !void {
    const delimiter = config.get("delimiter") orelse ",";
    const has_header = config.getBool("header") orelse true;

    var parser = csv.Parser.init(std.io.getStdIn().reader());
    parser.delimiter = delimiter[0];

    // Read header
    var headers: [][]const u8 = undefined;
    if (has_header) {
        headers = try parser.readRow();
    }

    // Stream rows as NDJSON
    while (try parser.next()) |row| {
        try writer.startObject();
        for (headers, row.fields) |key, value| {
            try writer.field(key, value);
        }
        try writer.endObject();
        try writer.newline();
    }
}

pub fn main() !void {
    try jn.run(plugin, .{ .reads = reads, .writes = writes });
}
```

---

## Phase 2: Core Zig Binary (Week 3-4)

### 2.1 Partial vs Full Core Replacement

#### Option A: Full Replacement
Replace entire `jn` CLI with Zig binary.

| Pros | Cons |
|------|------|
| Single binary, instant startup | Large effort (~3,000 lines) |
| No Python dependency for core | Must reimplement all resolution logic |
| Simpler deployment | Risk of behavior differences |

#### Option B: Partial Replacement (Recommended)
Replace hot path only, keep Python for complex logic.

```
┌─────────────────────────────────────────────────────────────┐
│                   jn-fast (Zig binary)                      │
│  • CLI parsing                                              │
│  • Address parsing                                          │
│  • Plugin discovery (from manifests)                        │
│  • Pipeline execution                                       │
│  • Simple pattern matching                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (fallback for complex cases)
┌─────────────────────────────────────────────────────────────┐
│                   jn-resolve (Python)                       │
│  • Profile resolution (HTTP auth, OAuth)                    │
│  • Complex address resolution                               │
│  • Plugin introspection                                     │
│  • Error message generation with suggestions                │
└─────────────────────────────────────────────────────────────┘
```

**Decision:** Start with Option B, evolve to Option A if needed.

### 2.2 Core Components to Implement

| Component | Zig Lines | C Libraries | Notes |
|-----------|-----------|-------------|-------|
| CLI parser | ~200 | - | `std.process.ArgIterator` |
| Address parser | ~400 | - | String parsing |
| Plugin discovery | ~300 | - | Dir scan, JSON manifest |
| Pattern matching | ~200 | PCRE2 | `@cImport("pcre2.h")` |
| Pipeline executor | ~400 | - | `std.process.Child` |
| Config builder | ~150 | - | Type inference |
| **Total** | **~1,650** | | |

### 2.3 C Libraries via @cImport

```zig
// Use PCRE2 for regex matching
const pcre2 = @cImport({
    @cInclude("pcre2.h");
});

fn matchPattern(pattern: []const u8, subject: []const u8) bool {
    var error_code: c_int = undefined;
    var error_offset: usize = undefined;

    const re = pcre2.pcre2_compile_8(
        pattern.ptr, pattern.len,
        0, &error_code, &error_offset, null
    );
    defer pcre2.pcre2_code_free_8(re);

    const match_data = pcre2.pcre2_match_data_create_from_pattern_8(re, null);
    defer pcre2.pcre2_match_data_free_8(match_data);

    const rc = pcre2.pcre2_match_8(
        re, subject.ptr, subject.len, 0, 0, match_data, null
    );

    return rc >= 0;
}
```

---

## Phase 3: Zig Plugins (Week 5-6)

### 3.1 Plugin Priority Order

1. **csv** - Most common, simple format
2. **json/jsonl** - Core interchange format
3. **gz** - Compression layer
4. **http** - Protocol plugin
5. **yaml** - Common config format
6. **toml** - Common config format

### 3.2 Library Dependencies

| Plugin | Zig Library | C Library Option | Notes |
|--------|-------------|------------------|-------|
| csv | [zig_csv](https://github.com/matthewtolman/zig_csv) | - | SIMD support |
| json | std.json | [simdjson](https://github.com/simdjson/simdjson) | 3+ GB/s with simdjson |
| jsonl | std.json | simdjson | Streaming NDJSON |
| gz | std.compress.gzip | zlib | Built-in to Zig std |
| http | [zig-curl](https://github.com/jiacai2050/zig-curl) | libcurl | TLS support |
| yaml | - | libyaml | Via @cImport |
| toml | - | - | Simple parser |

### 3.3 JSON Plugin with simdjson

For maximum performance, use [simdjson](https://github.com/simdjson/simdjson) via C interop:

```zig
const simdjson = @cImport({
    @cInclude("simdjson.h");
});

pub fn reads(config: jn.Config, writer: anytype) !void {
    var parser = simdjson.ondemand.parser{};

    // Use iterate_many for NDJSON streaming at 3+ GB/s
    var stream = simdjson.iterate_many(stdin_buffer);

    while (stream.next()) |doc| {
        // Re-serialize to ensure valid NDJSON output
        try writer.writeJson(doc);
        try writer.newline();
    }
}
```

### 3.4 HTTP Plugin

```zig
const curl = @import("zig-curl");

pub fn reads(config: jn.Config, writer: anytype) !void {
    const url = config.get("url") orelse return error.MissingUrl;
    const method = config.get("method") orelse "GET";

    var easy = curl.Easy.init();
    defer easy.deinit();

    try easy.setUrl(url);
    try easy.setMethod(method);

    // Stream response to stdout
    easy.setWriteCallback(struct {
        fn callback(data: []const u8, writer: anytype) usize {
            writer.writeAll(data) catch return 0;
            return data.len;
        }
    }.callback, writer);

    try easy.perform();
}
```

---

## Phase 4: Rust jq Plugin (Week 7-8)

### 4.1 Why Rust for jq?

- [jaq](https://github.com/01mf02/jaq) is a mature, fast jq implementation
- 30x faster startup than jq
- Security audited by Radically Open Security
- Can use as library (jaq-core)

### 4.2 Implementation

Location: `plugins/rust/jq/`

```rust
// plugins/rust/jq/src/main.rs
use jaq_core::{Ctx, RcIter, Val};
use jaq_interpret::FilterT;
use jn_plugin::{Plugin, Config, run};
use std::io::{BufRead, Write};

#[derive(Plugin)]
#[plugin(name = "jq", role = "filter", matches = [])]
struct JqPlugin;

impl JqPlugin {
    fn filters(&self, config: &Config) -> Result<(), Box<dyn std::error::Error>> {
        let expr = config.args.first()
            .ok_or("Missing jq expression")?;

        // Parse jq expression
        let mut defs = jaq_core::Definitions::core();
        let filter = jaq_parse::parse(&expr, jaq_parse::main())
            .map_err(|e| format!("Parse error: {:?}", e))?;

        let filter = defs.finish(filter, Vec::new(), &[]);

        // Process NDJSON stream
        let stdin = std::io::stdin();
        let stdout = std::io::stdout();
        let mut stdout = stdout.lock();

        for line in stdin.lock().lines() {
            let line = line?;
            let input: Val = serde_json::from_str(&line)?;

            let inputs = RcIter::new(std::iter::empty());
            let ctx = Ctx::new([], &inputs);

            for output in filter.run((ctx, input)) {
                let output = output?;
                serde_json::to_writer(&mut stdout, &output)?;
                writeln!(stdout)?;
            }
        }

        Ok(())
    }
}

fn main() {
    run::<JqPlugin>();
}
```

### 4.3 jaq Compatibility

jaq supports ~95% of jq syntax. Key differences:

| Feature | jq | jaq |
|---------|----|----|
| `limit(n; expr)` | ✅ | ✅ |
| `first`, `last` | ✅ | ✅ |
| `@base64d` | ✅ | ✅ |
| `$ENV` | ✅ | ✅ |
| `input`, `inputs` | ✅ | ✅ |
| SQL-style operators | ✅ | ❌ |
| `modulemeta` | ✅ | ❌ |

For JN's use cases (select, field access, comparisons), jaq is fully compatible.

---

## Phase 5: Integration & Testing (Week 9-10)

### 5.1 Discovery Integration

Update `jn` to discover plugins in priority order:

```python
# src/jn/plugins/discovery.py

def discover_plugins(plugin_dir: Path) -> Dict[str, PluginMetadata]:
    plugins = {}

    # 1. Binary plugins (Zig, Rust) - highest priority
    for binary in plugin_dir.glob("*"):
        if binary.is_file() and is_executable(binary):
            meta = load_or_generate_manifest(binary)
            if meta:
                plugins[meta.name] = meta

    # 2. Python plugins - lower priority (don't override binaries)
    for py_file in plugin_dir.rglob("*.py"):
        meta = parse_pep723(py_file)
        if meta and meta.name not in plugins:
            plugins[meta.name] = meta

    return plugins
```

### 5.2 Test Matrix

| Test | csv (Zig) | json (Zig) | jq (Rust) | http (Zig) |
|------|-----------|------------|-----------|------------|
| Basic read | ✅ | ✅ | ✅ | ✅ |
| Basic write | ✅ | ✅ | N/A | N/A |
| Streaming 1GB | ✅ | ✅ | ✅ | ✅ |
| Unicode | ✅ | ✅ | ✅ | ✅ |
| Malformed input | ✅ | ✅ | ✅ | ✅ |
| --jn-meta | ✅ | ✅ | ✅ | ✅ |
| Pipeline chain | ✅ | ✅ | ✅ | ✅ |

### 5.3 Performance Benchmarks

Target improvements over Python:

| Metric | Python | Zig/Rust | Target |
|--------|--------|----------|--------|
| Startup | 150-200ms | <5ms | 30x+ |
| CSV 1GB | 20s | 2s | 10x |
| JSON 1GB | 15s | 1.5s | 10x |
| jq filter | 50ms startup | <5ms | 10x |

---

## Phase 6: Python Plugin Retention (Ongoing)

### 6.1 Plugins Staying in Python

| Plugin | Reason |
|--------|--------|
| gmail | OAuth2 complexity, Google API client |
| mcp | JSON-RPC, complex protocol |
| duckdb | DuckDB Python bindings |
| xlsx | openpyxl library |
| markdown | mdutils library |
| table | tabulate library |
| xml | lxml library |

### 6.2 Python Core Library Updates

Ensure Python plugins use the same `jn_plugin` library pattern:

```python
# Migrate existing plugins to use jn_plugin
from jn_plugin import Plugin

plugin = Plugin(
    name="gmail",
    matches=[r"^gmail://"],
    role="protocol",
    manages_parameters=True,
)

@plugin.reader
def reads(url: str, config=None):
    # Existing gmail logic
    ...
```

---

## Directory Structure

```
jn/
├── src/jn/                    # Python framework (partial, for complex resolution)
├── core/                      # Zig core binary
│   ├── src/
│   │   ├── main.zig          # CLI entry
│   │   ├── address.zig       # Address parser
│   │   ├── discovery.zig     # Plugin discovery
│   │   ├── pipeline.zig      # Pipeline executor
│   │   └── pattern.zig       # Regex matching
│   └── build.zig
├── libs/
│   ├── python/jn_plugin/     # Python core library
│   ├── zig/jn-plugin/        # Zig core library
│   └── rust/jn-plugin/       # Rust core library
├── plugins/
│   ├── zig/
│   │   ├── csv/
│   │   ├── json/
│   │   ├── jsonl/
│   │   ├── gz/
│   │   ├── http/
│   │   ├── yaml/
│   │   └── toml/
│   ├── rust/
│   │   └── jq/
│   └── python/               # Symlink to jn_home/plugins
├── jn_home/plugins/          # Python plugins (existing)
└── spec/polyglot/            # Design docs
```

---

## Timeline Summary

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1-2 | Foundation | Core libraries (Python, Zig, Rust), CSV plugin PoC |
| 3-4 | Core Binary | Zig CLI, address parser, pipeline executor |
| 5-6 | Zig Plugins | json, jsonl, gz, http plugins |
| 7-8 | Rust Plugin | jq replacement using jaq |
| 9-10 | Integration | Discovery, testing, benchmarks |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Zig learning curve | Start with simple CSV plugin |
| C library integration | Use well-maintained libs (libcurl, PCRE2) |
| jaq compatibility | Test against JN's actual jq usage |
| Binary distribution | GitHub Actions for all platforms |
| Python fallback | Keep Python resolver for complex cases |

---

## Success Criteria

1. **Performance:** 10x improvement on CSV/JSON parsing
2. **Startup:** <10ms for simple commands (vs 150-200ms)
3. **Compatibility:** All existing tests pass
4. **Distribution:** Single binary for core + plugins
5. **Developer experience:** Clear docs for each language

---

## References

### Zig Libraries
- [zig_csv](https://github.com/matthewtolman/zig_csv) - CSV parser with SIMD
- [zig-curl](https://github.com/jiacai2050/zig-curl) - libcurl bindings
- [zimdjson](https://github.com/EzequielRamis/zimdjson) - simdjson port
- [std.json](https://github.com/ziglang/zig/blob/master/lib/std/json.zig) - Standard library JSON

### Rust Libraries
- [jaq](https://github.com/01mf02/jaq) - jq clone (30x faster startup)
- [jaq-core](https://crates.io/crates/jaq-core) - jaq as library

### C Libraries
- [simdjson](https://github.com/simdjson/simdjson) - 3+ GB/s JSON parsing
- [PCRE2](https://github.com/PCRE2Project/pcre2) - Regex library
- [libcurl](https://curl.se/libcurl/) - HTTP client
