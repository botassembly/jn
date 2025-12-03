# Phase 1 Task: Foundation Libraries

**Assignee**: First Developer
**Phase**: 1 of 11
**Status**: Ready to Start
**Estimated Scope**: 3 libraries, ~1000-1500 lines total

---

## Objective

Create three shared Zig libraries that eliminate boilerplate across all JN tools and plugins. These libraries will be used by every subsequent phase.

---

## Background

Read these documents first:
1. **[CLAUDE.md](/CLAUDE.md)** - Build commands, project structure
2. **[02-architecture.md](/spec/02-architecture.md)** - Component responsibilities
3. **[04-project-layout.md](/spec/04-project-layout.md)** - Where libraries go
4. **[08-streaming-backpressure.md](/spec/08-streaming-backpressure.md)** - I/O design patterns

Study these existing plugins to understand the patterns to extract:
- `plugins/zig/csv/main.zig` (~350 lines)
- `plugins/zig/json/main.zig` (~250 lines)
- `plugins/zig/gz/main.zig` (~175 lines)

---

## Deliverables

### 1. libjn-core (`libs/zig/jn-core/`)

**Purpose**: Streaming I/O and JSON handling

**Files to create**:
```
libs/zig/jn-core/
├── src/
│   ├── root.zig       # Public exports
│   ├── reader.zig     # Buffered stdin reader
│   ├── writer.zig     # Buffered stdout writer
│   ├── json.zig       # JSON parsing helpers
│   └── errors.zig     # Error handling, exit codes
└── build.zig
```

**Key APIs**:
```zig
// reader.zig
pub const StdinReader = struct {
    pub fn init() StdinReader;
    pub fn readLine(self: *StdinReader) ?[]const u8;
    // Uses 64KB buffer, handles Zig 0.15.2 API
};

// writer.zig
pub const StdoutWriter = struct {
    pub fn init() StdoutWriter;
    pub fn write(self: *StdoutWriter, data: []const u8) !void;
    pub fn writeLine(self: *StdoutWriter, line: []const u8) !void;
    pub fn flush(self: *StdoutWriter) !void;
    // Uses 8KB buffer, handles BrokenPipe gracefully
};

// json.zig
pub fn parseJson(allocator: Allocator, line: []const u8) !std.json.Value;
pub fn writeJsonLine(writer: *StdoutWriter, value: std.json.Value) !void;

// errors.zig
pub fn exitWithError(comptime fmt: []const u8, args: anytype) noreturn;
pub fn handleSigpipe() void;
```

**Tests**: Create `libs/zig/jn-core/src/test_*.zig` for each module.

---

### 2. libjn-cli (`libs/zig/jn-cli/`)

**Purpose**: Argument parsing

**Files to create**:
```
libs/zig/jn-cli/
├── src/
│   ├── root.zig       # Public exports
│   └── args.zig       # Argument parsing
└── build.zig
```

**Key APIs**:
```zig
// args.zig
pub const ArgParser = struct {
    pub fn init() ArgParser;

    // Register arguments
    pub fn addString(self: *ArgParser, name: []const u8, default: ?[]const u8) void;
    pub fn addBool(self: *ArgParser, name: []const u8) void;
    pub fn addInt(self: *ArgParser, name: []const u8, default: ?i64) void;

    // Parse
    pub fn parse(self: *ArgParser) !Args;

    // Result access
    pub const Args = struct {
        pub fn getString(self: Args, name: []const u8) ?[]const u8;
        pub fn getBool(self: Args, name: []const u8) bool;
        pub fn getInt(self: Args, name: []const u8) ?i64;
    };
};

// Standard args every plugin needs
pub fn addPluginArgs(parser: *ArgParser) void {
    parser.addString("mode", "read");  // --mode=read|write|raw
    parser.addBool("jn-meta");         // --jn-meta
    parser.addBool("help");            // --help
    parser.addBool("version");         // --version
}
```

---

### 3. libjn-plugin (`libs/zig/jn-plugin/`)

**Purpose**: Plugin manifest and entry point

**Files to create**:
```
libs/zig/jn-plugin/
├── src/
│   ├── root.zig       # Public exports
│   ├── meta.zig       # PluginMeta struct
│   └── manifest.zig   # --jn-meta JSON output
└── build.zig
```

**Key APIs**:
```zig
// meta.zig
pub const PluginMeta = struct {
    name: []const u8,
    version: []const u8,
    matches: []const []const u8,
    role: Role,
    modes: []const Mode,

    pub const Role = enum { format, protocol, compression, database };
    pub const Mode = enum { read, write, raw, profiles };
};

// manifest.zig
pub fn outputManifest(writer: anytype, meta: PluginMeta) !void;
// Outputs JSON: {"name":"csv","version":"0.1.0","matches":[".*\\.csv$"],...}

// root.zig - convenience wrapper
pub fn pluginMain(
    comptime meta: PluginMeta,
    comptime handlers: struct {
        read: ?fn() anyerror!void = null,
        write: ?fn() anyerror!void = null,
        raw: ?fn() anyerror!void = null,
    },
) !void {
    // 1. Parse args
    // 2. If --jn-meta, output manifest and exit
    // 3. Dispatch to handler based on --mode
}
```

---

## Build Integration

### Update Makefile

Add to root `Makefile`:
```makefile
# Zig libraries
zig-libs:
	cd libs/zig/jn-core && zig build
	cd libs/zig/jn-cli && zig build
	cd libs/zig/jn-plugin && zig build

zig-libs-test:
	cd libs/zig/jn-core && zig build test
	cd libs/zig/jn-cli && zig build test
	cd libs/zig/jn-plugin && zig build test
```

### Library build.zig pattern

Each library should follow this pattern:
```zig
const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    // Library module (for importing)
    const lib = b.addModule("jn-core", .{
        .root_source_file = b.path("src/root.zig"),
    });
    _ = lib;

    // Tests
    const tests = b.addTest(.{
        .root_source_file = b.path("src/root.zig"),
        .target = target,
        .optimize = optimize,
    });
    const run_tests = b.addRunArtifact(tests);
    const test_step = b.step("test", "Run unit tests");
    test_step.dependOn(&run_tests.step);
}
```

---

## Acceptance Criteria

### Must Have
- [ ] All three libraries compile with `zig build`
- [ ] All tests pass with `zig build test`
- [ ] Makefile targets work: `make zig-libs`, `make zig-libs-test`
- [ ] Libraries use Zig 0.15.2 compatible APIs (use `-fllvm` if needed)

### Code Quality
- [ ] No allocator leaks (use arena pattern for JSON)
- [ ] BrokenPipe handled gracefully (exit 0, not error)
- [ ] Clear error messages to stderr
- [ ] Each public function has a doc comment

### Validation
- [ ] Create `libs/zig/examples/minimal-plugin.zig` that uses all three libraries
- [ ] Example plugin compiles to <100KB binary
- [ ] Example plugin starts in <5ms

---

## Example: Minimal Plugin Using Libraries

After Phase 1, a plugin should look like this:

```zig
const std = @import("std");
const core = @import("jn-core");
const cli = @import("jn-cli");
const plugin = @import("jn-plugin");

const meta = plugin.PluginMeta{
    .name = "example",
    .version = "0.1.0",
    .matches = &.{".*\\.example$"},
    .role = .format,
    .modes = &.{ .read, .write },
};

pub fn main() !void {
    try plugin.pluginMain(meta, .{
        .read = readMode,
        .write = writeMode,
    });
}

fn readMode() !void {
    var reader = core.StdinReader.init();
    var writer = core.StdoutWriter.init();
    defer writer.flush() catch {};

    while (reader.readLine()) |line| {
        // Process line
        try writer.writeLine(line);
    }
}

fn writeMode() !void {
    // Similar pattern
}
```

Compare to current `csv/main.zig` which is ~350 lines. The refactored version should be ~50 lines.

---

## Getting Started

1. Create the directory structure:
   ```bash
   mkdir -p libs/zig/jn-core/src
   mkdir -p libs/zig/jn-cli/src
   mkdir -p libs/zig/jn-plugin/src
   mkdir -p libs/zig/examples
   ```

2. Start with libjn-core (most important, others depend on it)

3. Study `plugins/zig/csv/main.zig` for patterns to extract

4. Test frequently: `zig build test`

5. Validate with the example plugin before marking complete

---

## Notes

- **Zig version**: 0.15.2 (use `-fllvm` flag for x86 backend)
- **Build command**: `zig build-exe ... -fllvm -O ReleaseFast`
- **Don't over-engineer**: Start simple, add features as needed
- **Reference**: Existing plugins show real-world patterns

---

## Questions?

If blocked, check:
1. `make test` - ensure Python tests still pass
2. `make check` - ensure quality gates pass
3. Existing plugin code for patterns
