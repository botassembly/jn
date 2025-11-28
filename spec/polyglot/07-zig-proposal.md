# Zig for JN Core Plugins

**Thesis:** Zig may be the optimal choice for JN's core format plugins, offering Rust-level performance with Go-level simplicity.

---

## Why Zig?

### Comparison Matrix

| Metric | Rust | Go | Zig | C |
|--------|------|-----|-----|---|
| Binary size | 2-5MB | 5-10MB | **100-500KB** | 50-200KB |
| Startup time | <5ms | <5ms | **<1ms** | <1ms |
| Compile time | 10-30s | <1s | **<5s** | Varies |
| Cross-compile | Needs `cross` | Easy | **Trivial** | Hard |
| Learning curve | Steep | Gentle | **Moderate** | Moderate |
| C interop | Via FFI | Via CGo | **Native** | N/A |
| Memory safety | Compile-time | GC | **Runtime checks** | Manual |
| SIMD | Via intrinsics | Limited | **First-class** | Via intrinsics |

### Zig's Killer Features for JN

**1. Trivial Cross-Compilation**
```bash
# Build for all targets from any host
zig build-exe src/csv.zig -target x86_64-linux-gnu
zig build-exe src/csv.zig -target aarch64-linux-gnu
zig build-exe src/csv.zig -target x86_64-macos
zig build-exe src/csv.zig -target aarch64-macos
zig build-exe src/csv.zig -target x86_64-windows-gnu
```
No Docker, no `cross`, no toolchain setup. Just works.

**2. Tiny Binaries**
```
csv_ (Zig):  ~150KB
csv_ (Rust): ~2.5MB
csv_ (Go):   ~5MB
```
Faster downloads, faster startup, smaller distribution.

**3. Native C Interop**
```zig
// Import any C header directly
const c = @cImport({
    @cInclude("zlib.h");
    @cInclude("libcsv.h");
});

// Use C functions directly
const stream = c.gzopen(path, "rb");
defer c.gzclose(stream);
```
Wrap existing high-performance C libraries without FFI overhead.

**4. First-Class SIMD**
```zig
const std = @import("std");
const Vector = std.meta.Vector;

// SIMD CSV delimiter scanning
fn findDelimiters(data: []const u8) []usize {
    const chunk: Vector(32, u8) = data[0..32].*;
    const delim: Vector(32, u8) = @splat(32, @as(u8, ','));
    const matches = chunk == delim;
    // ...
}
```
Built into the language, not a separate crate.

**5. Comptime (Compile-Time Execution)**
```zig
// Generate JSON schema at compile time
const meta = comptime blk: {
    break :blk .{
        .name = "csv",
        .matches = &[_][]const u8{ ".*\\.csv$", ".*\\.tsv$" },
    };
};
```
Zero runtime overhead for metadata.

---

## Zig Plugin Architecture

### Core Library (`jn-plugin-zig/`)

```
jn-plugin-zig/
├── build.zig           # Build configuration
├── src/
│   ├── plugin.zig      # Core plugin framework
│   ├── ndjson.zig      # NDJSON streaming I/O
│   ├── cli.zig         # Argument parsing
│   └── simd.zig        # SIMD utilities
└── plugins/
    ├── csv.zig
    ├── json.zig
    ├── gz.zig
    └── ...
```

### Plugin Framework (`src/plugin.zig`)

```zig
const std = @import("std");
const json = std.json;

pub const PluginMeta = struct {
    name: []const u8,
    version: []const u8 = "0.1.0",
    description: []const u8 = "",
    matches: []const []const u8,
    modes: []const []const u8,
    supports_raw: bool = false,
    manages_parameters: bool = false,
    supports_container: bool = false,
};

pub fn Plugin(comptime meta: PluginMeta) type {
    return struct {
        const Self = @This();

        pub fn run(
            readFn: ?fn (config: Config) anyerror!void,
            writeFn: ?fn (config: Config) anyerror!void,
        ) void {
            const args = parseArgs() catch |err| {
                std.debug.print("Error: {}\n", .{err});
                std.process.exit(1);
            };

            if (args.jn_meta) {
                outputMeta(meta);
                return;
            }

            const result = switch (args.mode.?) {
                .read => if (readFn) |f| f(args.config) else error.ModeNotSupported,
                .write => if (writeFn) |f| f(args.config) else error.ModeNotSupported,
                .raw => error.ModeNotSupported,
            };

            result catch |err| {
                std.debug.print("Error: {}\n", .{err});
                std.process.exit(1);
            };
        }

        fn outputMeta(m: PluginMeta) void {
            const stdout = std.io.getStdOut().writer();
            json.stringify(m, .{}, stdout) catch return;
            stdout.writeByte('\n') catch return;
        }
    };
}
```

### NDJSON I/O (`src/ndjson.zig`)

```zig
const std = @import("std");
const json = std.json;

pub const NdjsonReader = struct {
    reader: std.fs.File.Reader,
    buf: [64 * 1024]u8 = undefined,

    pub fn init() NdjsonReader {
        return .{ .reader = std.io.getStdIn().reader() };
    }

    pub fn next(self: *NdjsonReader, allocator: std.mem.Allocator) !?json.Value {
        const line = self.reader.readUntilDelimiter(&self.buf, '\n') catch |err| {
            if (err == error.EndOfStream) return null;
            return err;
        };

        if (line.len == 0) return self.next(allocator);

        return try json.parseFromSlice(json.Value, allocator, line, .{});
    }
};

pub const NdjsonWriter = struct {
    writer: std.fs.File.Writer,
    buf: std.io.BufferedWriter(64 * 1024, std.fs.File.Writer),

    pub fn init() NdjsonWriter {
        const stdout = std.io.getStdOut();
        return .{
            .writer = stdout.writer(),
            .buf = std.io.bufferedWriter(stdout.writer()),
        };
    }

    pub fn write(self: *NdjsonWriter, value: anytype) !void {
        try json.stringify(value, .{}, self.buf.writer());
        try self.buf.writer().writeByte('\n');
    }

    pub fn flush(self: *NdjsonWriter) !void {
        try self.buf.flush();
    }
};
```

### Example: CSV Plugin (`plugins/csv.zig`)

```zig
const std = @import("std");
const plugin = @import("../src/plugin.zig");
const ndjson = @import("../src/ndjson.zig");

const csv_plugin = plugin.Plugin(.{
    .name = "csv",
    .description = "Parse CSV/TSV files and convert to/from NDJSON",
    .matches = &[_][]const u8{ ".*\\.csv$", ".*\\.tsv$", ".*\\.txt$" },
    .modes = &[_][]const u8{ "read", "write" },
});

pub fn main() void {
    csv_plugin.run(readCsv, writeCsv);
}

fn readCsv(config: plugin.Config) !void {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const allocator = arena.allocator();

    const stdin = std.io.getStdIn().reader();
    var writer = ndjson.NdjsonWriter.init();
    defer writer.flush() catch {};

    // Read header
    var header_buf: [4096]u8 = undefined;
    const header_line = try stdin.readUntilDelimiter(&header_buf, '\n');
    var headers = std.ArrayList([]const u8).init(allocator);

    var header_iter = std.mem.split(u8, header_line, &[_]u8{config.delimiter});
    while (header_iter.next()) |field| {
        try headers.append(try allocator.dupe(u8, field));
    }

    // Read rows
    var line_buf: [64 * 1024]u8 = undefined;
    var count: usize = 0;

    while (stdin.readUntilDelimiter(&line_buf, '\n')) |line| {
        var record = std.StringHashMap([]const u8).init(allocator);

        var field_iter = std.mem.split(u8, line, &[_]u8{config.delimiter});
        var i: usize = 0;
        while (field_iter.next()) |field| : (i += 1) {
            if (i < headers.items.len) {
                try record.put(headers.items[i], field);
            }
        }

        try writer.write(record);

        count += 1;
        if (config.limit) |limit| {
            if (count >= limit) break;
        }
    } else |err| {
        if (err != error.EndOfStream) return err;
    }
}

fn writeCsv(config: plugin.Config) !void {
    // ... write implementation
}
```

### Build Configuration (`build.zig`)

```zig
const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    // Build all plugins
    const plugins = [_][]const u8{ "csv", "json", "gz", "yaml", "toml" };

    for (plugins) |name| {
        const exe = b.addExecutable(.{
            .name = name ++ "_",
            .root_source_file = .{ .path = "plugins/" ++ name ++ ".zig" },
            .target = target,
            .optimize = optimize,
        });

        // Link C libraries if needed
        if (std.mem.eql(u8, name, "gz")) {
            exe.linkSystemLibrary("z");
        }

        b.installArtifact(exe);
    }

    // Cross-compile targets
    const targets = [_]std.zig.CrossTarget{
        .{ .cpu_arch = .x86_64, .os_tag = .linux },
        .{ .cpu_arch = .aarch64, .os_tag = .linux },
        .{ .cpu_arch = .x86_64, .os_tag = .macos },
        .{ .cpu_arch = .aarch64, .os_tag = .macos },
        .{ .cpu_arch = .x86_64, .os_tag = .windows },
    };

    const cross_step = b.step("cross", "Build for all platforms");
    for (targets) |t| {
        // ... add cross-compilation steps
    }
}
```

---

## Build & Distribution

### Single Command Cross-Compile

```bash
# Build all plugins for all platforms
zig build cross -Doptimize=ReleaseFast

# Output:
# zig-out/
# ├── x86_64-linux/
# │   ├── csv_
# │   ├── json_
# │   └── gz_
# ├── aarch64-linux/
# ├── x86_64-macos/
# ├── aarch64-macos/
# └── x86_64-windows/
```

### CI Simplification

```yaml
# .github/workflows/release.yml
jobs:
  build:
    runs-on: ubuntu-latest  # Single runner for ALL platforms
    steps:
      - uses: actions/checkout@v4

      - name: Install Zig
        uses: goto-bus-stop/setup-zig@v2

      - name: Build all platforms
        run: zig build cross -Doptimize=ReleaseFast

      - name: Package
        run: |
          for platform in x86_64-linux aarch64-linux x86_64-macos aarch64-macos x86_64-windows; do
            tar -czvf jn-plugins-$platform.tar.gz -C zig-out/$platform .
          done
```

**No matrix builds needed.** One Ubuntu runner builds all 5 platforms.

---

## Performance Expectations

### vs Rust

| Operation | Rust | Zig | Notes |
|-----------|------|-----|-------|
| CSV parse (1GB) | ~2s | ~2s | Equivalent |
| JSON parse (1GB) | ~1.5s | ~1.5s | Equivalent |
| Startup | <5ms | **<1ms** | 5x faster |
| Binary size | 2-5MB | **100-500KB** | 10x smaller |
| Compile time | 10-30s | **<5s** | 5x faster |

### vs Go

| Operation | Go | Zig | Notes |
|-----------|-----|-----|-------|
| CSV parse (1GB) | ~3-4s | **~2s** | 50% faster |
| JSON parse (1GB) | ~2-3s | **~1.5s** | 50% faster |
| Startup | <5ms | **<1ms** | 5x faster |
| Binary size | 5-10MB | **100-500KB** | 20x smaller |

---

## Migration Path

### Phase 1: Proof of Concept
```
1. Implement csv_ in Zig
2. Benchmark against Python/Rust
3. Test cross-compilation
4. Validate --jn-meta integration
```

### Phase 2: Core Plugins
```
csv_   → Zig
json_  → Zig
gz_    → Zig (with zlib)
```

### Phase 3: Extended Plugins
```
yaml_  → Zig
toml_  → Zig
xml_   → Zig (with libxml2 or pure Zig)
```

### Keep in Python/Go
```
http_     → Python (requests, profile resolution)
duckdb_   → Python (duckdb-python bindings)
mcp_      → Python (async MCP protocol)
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Pre-1.0 API changes | Pin Zig version, update during releases |
| Smaller ecosystem | Use C libraries where needed |
| Fewer contributors know Zig | Good docs, simple patterns |
| Debug tooling | LLDB works, Zig has improving tools |

---

## Conclusion

Zig offers the best combination for JN's core plugins:

| Need | Zig Delivers |
|------|--------------|
| Fast parsing | SIMD, zero-copy, C-level speed |
| Small binaries | 100-500KB (10x smaller than Rust) |
| Fast startup | <1ms (5x faster than Rust) |
| Easy cross-compile | Single command, no toolchains |
| Fast iteration | <5s compile (5x faster than Rust) |
| C library access | Native `@cImport` |

**Recommendation:** Start with a Zig CSV plugin proof-of-concept to validate the approach.
