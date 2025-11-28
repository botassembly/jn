# Zig Replacement Evaluation for JN Core

**Status:** Evaluation
**Date:** 2024-01
**Purpose:** Analyze what parts of JN core could be replaced with Zig, benefits, and difficulties

## Current Core Architecture

### Code Size Analysis

| Component | Lines | Description |
|-----------|-------|-------------|
| CLI Commands | ~1,400 | Click-based CLI (cat, put, filter, etc.) |
| Addressing | ~800 | Address parsing and resolution |
| Plugin System | ~500 | Discovery, registry, service |
| Profile System | ~1,200 | HTTP, Gmail, MCP profiles |
| Utilities | ~600 | Filtering, introspection, streaming |
| Checker | ~500 | AST-based plugin validation |
| Shell | ~200 | jc integration |
| **Total** | **~5,200** | Core framework |

### Current Execution Flow

```
User Command
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  jn CLI (Python + Click)                                     │
│  ├── Parse arguments                                         │
│  ├── Resolve home/plugin directories                         │
│  └── Dispatch to command handler                             │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  Address Parser (parser.py)                                  │
│  ├── Parse address[~format][?params]                         │
│  ├── Detect compression (.gz, .bz2)                          │
│  └── Return Address object                                   │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  Address Resolver (resolver.py)                              │
│  ├── Load plugin cache                                       │
│  ├── Match address to plugin(s)                              │
│  ├── Resolve profiles (HTTP auth, etc.)                      │
│  └── Plan execution stages                                   │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  Pipeline Execution (cat.py, put.py)                         │
│  ├── Fork plugin processes (uv run --script)                 │
│  ├── Connect via pipes                                       │
│  ├── Handle backpressure                                     │
│  └── Wait for completion                                     │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  Plugins (Python scripts via UV)                             │
│  ├── csv_.py, json_.py, etc.                                 │
│  ├── Read stdin → NDJSON stdout                              │
│  └── NDJSON stdin → format stdout                            │
└──────────────────────────────────────────────────────────────┘
```

---

## Component-by-Component Analysis

### 1. CLI Entry Point (`cli/main.py`)

**Current:** Click-based argument parsing (~70 lines)

**Zig Replacement:**
- Use `std.process.ArgIterator` for arg parsing
- Implement subcommand dispatch
- Handle --home global option

**Difficulty:** Low
**Benefit:** High - instant startup vs ~200ms Python

**Zig Example:**
```zig
const std = @import("std");

pub fn main() !void {
    var args = std.process.args();
    _ = args.skip(); // skip program name

    const subcommand = args.next() orelse {
        try usage();
        return;
    };

    if (std.mem.eql(u8, subcommand, "cat")) {
        try catCommand(&args);
    } else if (std.mem.eql(u8, subcommand, "put")) {
        try putCommand(&args);
    } else if (std.mem.eql(u8, subcommand, "filter")) {
        try filterCommand(&args);
    } else {
        try std.io.getStdErr().writer().print("Unknown command: {s}\n", .{subcommand});
    }
}
```

---

### 2. Address Parser (`addressing/parser.py`)

**Current:** 339 lines of Python string parsing

**Zig Replacement:**
- String slicing and pattern matching
- URL-style query string parsing
- Compression detection

**Difficulty:** Low-Medium
**Benefit:** High - faster parsing, no Python startup

**What translates well:**
- `_determine_type()` - simple prefix checks
- `_parse_query_string()` - character iteration
- Compression suffix detection

**Zig Example:**
```zig
const AddressType = enum {
    stdio,
    file,
    protocol,
    profile,
    plugin,
};

const Address = struct {
    raw: []const u8,
    base: []const u8,
    format_override: ?[]const u8,
    compression: ?[]const u8,
    addr_type: AddressType,
    parameters: std.StringHashMap([]const u8),
};

pub fn parseAddress(allocator: std.mem.Allocator, raw: []const u8) !Address {
    var addr = Address{
        .raw = raw,
        .base = raw,
        .format_override = null,
        .compression = null,
        .addr_type = .file,
        .parameters = std.StringHashMap([]const u8).init(allocator),
    };

    // Parse format override (~format)
    if (std.mem.lastIndexOf(u8, raw, "~")) |tilde_idx| {
        addr.base = raw[0..tilde_idx];
        const format_part = raw[tilde_idx + 1..];

        // Check for parameters after format
        if (std.mem.indexOf(u8, format_part, "?")) |q_idx| {
            addr.format_override = format_part[0..q_idx];
            try parseQueryString(allocator, format_part[q_idx + 1..], &addr.parameters);
        } else {
            addr.format_override = format_part;
        }
    }

    // Detect compression
    const compressions = [_][]const u8{ ".gz", ".bz2", ".xz" };
    for (compressions) |ext| {
        if (std.mem.endsWith(u8, addr.base, ext)) {
            addr.compression = ext[1..];
            addr.base = addr.base[0 .. addr.base.len - ext.len];
            break;
        }
    }

    // Determine type
    addr.addr_type = determineType(addr.base);

    return addr;
}

fn determineType(base: []const u8) AddressType {
    if (std.mem.eql(u8, base, "-") or
        std.mem.eql(u8, base, "stdin") or
        std.mem.eql(u8, base, "stdout")) {
        return .stdio;
    }
    if (base.len > 0 and base[0] == '@') {
        if (std.mem.indexOf(u8, base, "/") != null) {
            return .profile;
        }
        return .plugin;
    }
    if (std.mem.indexOf(u8, base, "://") != null) {
        return .protocol;
    }
    return .file;
}
```

---

### 3. Plugin Discovery (`plugins/discovery.py`)

**Current:** 208 lines - PEP 723 parsing, caching

**Zig Replacement:**
- Directory scanning
- Regex matching for PEP 723 metadata
- JSON cache read/write
- Manifest auto-generation (`--jn-meta`)

**Difficulty:** Medium
**Benefit:** Medium - discovery is one-time cost, but cache loading is per-command

**Key operations:**
1. Scan `$JN_HOME/plugins/` for `.py` and binary files
2. Parse PEP 723 TOML from Python files
3. Run `--jn-meta` for binaries
4. Cache results in JSON

**Zig has good support for:**
- Directory iteration (`std.fs.IterableDir`)
- Regex (via C interop with PCRE)
- JSON parsing (`std.json`)
- Process spawning (`std.process.Child`)

---

### 4. Plugin Registry (`plugins/registry.py`)

**Current:** 70 lines - pattern matching

**Zig Replacement:**
- Compile regex patterns at init
- Match against source addresses
- Return sorted by specificity

**Difficulty:** Low (with regex library)
**Benefit:** Medium

**Note:** Zig doesn't have built-in regex. Options:
1. Use PCRE via `@cImport`
2. Use simpler glob matching (sufficient for most plugins)
3. Implement subset of regex needed

---

### 5. Address Resolver (`addressing/resolver.py`)

**Current:** 802 lines - complex resolution logic

**Zig Replacement Analysis:**

| Function | Lines | Difficulty | Notes |
|----------|-------|------------|-------|
| `resolve()` | 40 | Low | Calls helpers |
| `plan_execution()` | 180 | High | Complex staging logic |
| `_find_plugin()` | 100 | Medium | Type-based dispatch |
| `_find_plugin_by_*` | 200 | Medium | Pattern matching |
| `_build_config()` | 80 | Low | Type inference |
| `_resolve_url_and_headers()` | 100 | High | Profile resolution |

**Difficulty:** High
**Benefit:** Medium - resolution is fast enough in Python

**Challenges:**
- Complex conditional logic
- Error messages with suggestions
- Profile resolution (HTTP auth, Gmail OAuth)

---

### 6. Pipeline Execution (`cli/commands/cat.py`)

**Current:** 397 lines - subprocess orchestration

**Zig Replacement:**
- Fork/exec plugin processes
- Pipe management
- Signal handling (SIGPIPE)

**Difficulty:** Medium
**Benefit:** High - this is the hot path

**Zig pipeline execution:**
```zig
pub fn executePipeline(stages: []const ExecutionStage) !void {
    var procs: [8]std.process.Child = undefined;
    var proc_count: usize = 0;

    var prev_stdout: ?std.fs.File = null;

    for (stages) |stage, i| {
        const is_last = i == stages.len - 1;

        var child = std.process.Child.init(stage.argv, std.heap.page_allocator);

        // Connect stdin
        if (prev_stdout) |stdout| {
            child.stdin_behavior = .{ .pipe = stdout };
        } else if (stage.stdin_file) |file| {
            child.stdin_behavior = .{ .pipe = file };
        }

        // Connect stdout
        if (!is_last) {
            child.stdout_behavior = .pipe;
        }

        child.spawn() catch |err| {
            return error.SpawnFailed;
        };

        procs[proc_count] = child;
        proc_count += 1;

        prev_stdout = child.stdout;
    }

    // Wait for all processes
    for (procs[0..proc_count]) |*proc| {
        _ = proc.wait();
    }
}
```

---

### 7. Profile System (`profiles/`)

**Current:** ~1,200 lines - HTTP, Gmail, MCP

**Zig Replacement:**

| Component | Lines | Zig Difficulty | Recommendation |
|-----------|-------|----------------|----------------|
| Profile path resolution | 200 | Low | Replace |
| HTTP profile loading | 200 | Low | Replace |
| HTTP request building | 200 | Medium | Replace |
| Gmail OAuth flow | 150 | Very High | Keep Python |
| MCP protocol | 300 | High | Keep Python |

**Recommendation:** Replace path resolution and HTTP profile loading with Zig. Keep OAuth and MCP in Python plugins.

---

### 8. Filtering (`filtering.py`)

**Current:** 260 lines - jq filter construction

**Zig Replacement:**
- Parse filter parameters
- Build jq expressions
- Type inference

**Difficulty:** Low
**Benefit:** Low (filtering delegates to jq anyway)

**Recommendation:** Low priority. The actual filtering work is done by jq.

---

### 9. Plugin Checker (`checker/`)

**Current:** ~500 lines - AST-based validation

**Zig Replacement:** Not recommended

**Reason:** Python AST analysis requires Python. The checker validates Python plugin code structure and security patterns. This fundamentally needs Python's AST module.

**Alternative:** If we want to check non-Python plugins:
- Define JSON/YAML security rules
- Check at build time (in plugin's build system)
- Runtime manifest validation only

---

### 10. Introspection (`introspection.py`)

**Current:** 137 lines - plugin function inspection

**Zig Replacement:** Not recommended

**Reason:** Uses Python's `importlib` and `inspect` modules to extract parameter names from plugin functions. This is Python-specific.

**Alternative with `--jn-meta`:**
- Plugins declare config params in metadata
- No runtime introspection needed
- Zig can parse JSON metadata

---

## Replacement Strategy Matrix

| Component | Lines | Zig? | Benefit | Difficulty | Priority |
|-----------|-------|------|---------|------------|----------|
| CLI entry | 70 | ✅ | High | Low | 1 |
| Address parser | 340 | ✅ | High | Low | 1 |
| Pipeline exec | 400 | ✅ | High | Medium | 1 |
| Plugin discovery | 210 | ✅ | Medium | Medium | 2 |
| Pattern registry | 70 | ✅ | Medium | Low | 2 |
| Profile paths | 200 | ✅ | Medium | Low | 2 |
| HTTP profiles | 200 | ✅ | Medium | Medium | 3 |
| Filtering | 260 | ⚠️ | Low | Low | 4 |
| Address resolver | 800 | ⚠️ | Medium | High | 3 |
| Gmail/MCP | 400 | ❌ | Low | Very High | - |
| Checker | 500 | ❌ | N/A | N/A | - |
| Introspection | 140 | ❌ | N/A | N/A | - |

Legend:
- ✅ = Replace with Zig
- ⚠️ = Partial replacement or defer
- ❌ = Keep Python

---

## Proposed Architecture

### Phase 1: Core Binary (Priority 1)

Replace with single `jn` Zig binary:

```
jn (Zig binary)
├── CLI parsing (subcommands, global options)
├── Address parsing (address[~format][?params])
├── Plugin discovery (scan dirs, parse manifests)
├── Pipeline execution (fork/exec, pipes)
└── Context resolution (JN_HOME, paths)
```

**Estimated Zig code:** ~1,500 lines
**Replaces Python:** ~1,000 lines
**Remaining Python:** ~4,200 lines (profiles, checker, resolver)

### Phase 2: Resolver & Profiles (Priority 2-3)

```
jn (Zig binary)
├── ... Phase 1 ...
├── Pattern registry (regex matching)
├── Profile resolution (read JSON configs)
└── HTTP request building
```

**Estimated Zig code:** ~2,500 lines
**Replaces Python:** ~2,000 lines
**Remaining Python:** ~2,200 lines (Gmail, MCP, checker)

### Phase 3: Steady State

Keep in Python (as plugins or framework):
- Gmail plugin (OAuth complexity)
- MCP plugin (JSON-RPC complexity)
- Plugin checker (Python AST)
- Complex profile logic (discovery, search)

---

## Benefits Summary

### Performance

| Metric | Python | Zig | Improvement |
|--------|--------|-----|-------------|
| CLI startup | 150-200ms | <5ms | 30-40x |
| Address parse | 1ms | <0.01ms | 100x |
| Plugin discovery (cached) | 10ms | <1ms | 10x |
| Pipeline fork | 50ms | <5ms | 10x |
| Binary size | N/A (interpreter) | <1MB | Standalone |

### User Experience

1. **Instant startup** - Commands feel native, not "Python slow"
2. **Single binary** - No Python/UV dependency for core operations
3. **Cross-platform** - One build produces all platform binaries
4. **Smaller install** - Core jn is <1MB vs Python environment

### Developer Experience

1. **Simple deployment** - Copy single binary
2. **Predictable performance** - No GC pauses
3. **Safer code** - Compile-time memory safety
4. **Easier debugging** - Direct system calls visible

---

## Difficulties & Risks

### Technical Challenges

1. **Regex Support**
   - Zig has no built-in regex
   - Need PCRE via `@cImport` or custom implementation
   - Alternative: Use glob patterns for most matches

2. **JSON Parsing**
   - `std.json` is strict and verbose
   - Need helper functions for common patterns
   - Error messages less friendly than Python

3. **Error Handling**
   - Must handle every error explicitly
   - Error messages need manual crafting
   - Python's exceptions are more convenient

4. **String Manipulation**
   - No garbage collection means manual allocation
   - String building is verbose
   - UTF-8 handling requires care

### Migration Risks

1. **Feature Parity**
   - All Python behaviors must be replicated
   - Edge cases discovered over time
   - Need comprehensive test suite

2. **Maintenance Burden**
   - Two codebases during transition
   - Team needs Zig expertise
   - Documentation updates

3. **Plugin Compatibility**
   - Plugins expect Python framework (UV)
   - Must maintain exact CLI contract
   - Config passing must match

---

## Recommendation

### Start with Phase 1

Focus on highest-impact, lowest-difficulty components:

1. **CLI entry** - Immediate startup improvement
2. **Address parsing** - Well-defined, testable
3. **Pipeline execution** - Core functionality, performance-critical
4. **Plugin discovery** - With manifest auto-generation

### Keep Python For

1. **Complex plugins** - Gmail, MCP (OAuth, JSON-RPC)
2. **Plugin checker** - Requires Python AST
3. **Advanced resolution** - Profile discovery, suggestions

### Hybrid Architecture

```
┌─────────────────────────────────────────────────────┐
│                   jn (Zig binary)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │ CLI Parser  │  │ Address     │  │ Pipeline   │  │
│  │             │  │ Parser      │  │ Executor   │  │
│  └─────────────┘  └─────────────┘  └────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │ Plugin      │  │ Pattern     │  │ Profile    │  │
│  │ Discovery   │  │ Registry    │  │ Resolver   │  │
│  └─────────────┘  └─────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│              Plugins (Any Language)                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ csv_.zig │  │ json_.zig│  │ http_.py │          │
│  └──────────┘  └──────────┘  └──────────┘          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ gz_.zig  │  │ yaml_.zig│  │ gmail_.py│          │
│  └──────────┘  └──────────┘  └──────────┘          │
└─────────────────────────────────────────────────────┘
```

### Timeline Estimate

| Phase | Components | Zig Lines | Duration |
|-------|------------|-----------|----------|
| 1 | Core binary | ~1,500 | 2-3 weeks |
| 2 | Discovery + Registry | ~500 | 1 week |
| 3 | Resolver + Profiles | ~1,000 | 2 weeks |
| **Total** | | **~3,000** | **5-6 weeks** |

---

## Next Steps

1. **Create Zig proof-of-concept** for `jn cat file.csv`
   - CLI parsing
   - Address parsing
   - Plugin discovery (from manifest)
   - Pipeline execution

2. **Validate cross-compilation**
   - Build for all platforms from one machine
   - Test binary sizes and startup times

3. **Define test suite**
   - Port Python tests to shell scripts
   - Ensure behavioral parity

4. **Migrate incrementally**
   - Start with `jn cat` (most used)
   - Add `jn put`, `jn filter`
   - Keep Python as fallback during transition
