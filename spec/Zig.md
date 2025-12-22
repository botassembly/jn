# Zig Compilation Notes for JN

This document captures Zig-specific configuration, compilation requirements, and known issues for the JN project.

---

## Zig Version

**Target version: Zig 0.15.2**

| Location | Version | Notes |
|----------|---------|-------|
| `Makefile` | 0.15.2 | Primary build configuration |
| GitHub Actions CI | 0.15.2 | Release builds |
| PyPI package (`uv.lock`) | 0.15.1 | Python-managed Zig |

The codebase includes compatibility shims for both 0.15.1 and 0.15.2 API differences.

---

## Critical: The `-fllvm` Flag

**All Zig builds in this project MUST use `-fllvm`** to avoid panics.

### Why

Zig 0.15.x's native x86 backend has unimplemented features that trigger `TODO` panics at compile time or runtime. The LLVM backend is stable and fully functional.

### Evidence

From `spec/opendal-analysis.md`:
> Must use `-fllvm` flag (Zig 0.15.2 native x86 backend has TODO panics).

From `zq/build.zig`:
```zig
// Use LLVM backend for stable builds (x86 backend has some TODO panics in 0.15.x)
```

### How to Apply

**Command-line builds:**
```bash
zig build-exe main.zig -fllvm -O ReleaseFast -femit-bin=output
```

**In `build.zig` files:**
```zig
const exe = b.addExecutable(.{
    .name = "my-tool",
    .root_source_file = b.path("src/main.zig"),
    .target = target,
    .optimize = optimize,
    .use_llvm = true,  // Required for stability
});
```

---

## Standard Build Commands

All JN Zig builds use this pattern:

```bash
zig build-exe <source> -fllvm -O ReleaseFast -femit-bin=<output>
```

### Examples

```bash
# ZQ filter engine
cd zq && zig build-exe src/main.zig -fllvm -O ReleaseFast -femit-bin=zig-out/bin/zq

# Plugins (with module imports)
cd plugins/zig/csv && zig build-exe -fllvm -O ReleaseFast \
    --mod jn-core:../../../libs/zig/jn-core/src/root.zig \
    --mod jn-cli:../../../libs/zig/jn-cli/src/root.zig \
    --mod jn-plugin:../../../libs/zig/jn-plugin/src/root.zig \
    --deps jn-core,jn-cli,jn-plugin \
    -femit-bin=bin/csv

# CLI tools
cd tools/zig/jn-cat && zig build-exe -fllvm -O ReleaseFast \
    --mod jn-core:../../../libs/zig/jn-core/src/root.zig \
    --mod jn-cli:../../../libs/zig/jn-cli/src/root.zig \
    --mod jn-plugin:../../../libs/zig/jn-plugin/src/root.zig \
    --mod jn-address:../../../libs/zig/jn-address/src/root.zig \
    --mod jn-profile:../../../libs/zig/jn-profile/src/root.zig \
    --mod jn-discovery:../../../libs/zig/jn-discovery/src/root.zig \
    --deps jn-core,jn-cli,jn-plugin,jn-address,jn-profile,jn-discovery \
    -femit-bin=bin/jn-cat
```

### Running Tests

```bash
# Test a library
cd libs/zig/jn-core && zig test src/root.zig -fllvm

# Test a plugin
cd plugins/zig/csv && zig test -fllvm $(PLUGIN_MODULES)

# Test ZQ
cd zq && zig test src/main.zig -fllvm
```

---

## Zig 0.15.x API Compatibility

### Line Reading API Change

The `takeDelimiter` API changed between 0.15.1 and 0.15.2:

| Version | Function | EOF Behavior |
|---------|----------|--------------|
| 0.15.1 | `takeDelimiterExclusive` | Throws `EndOfStream` |
| 0.15.2+ | `takeDelimiter` | Returns `null` |

**Compatibility pattern** (from `libs/zig/jn-core/src/reader.zig`):

```zig
const builtin = @import("builtin");

pub fn readLineRaw(reader: anytype) ?[]u8 {
    if (comptime builtin.zig_version.order(.{ .major = 0, .minor = 15, .patch = 2 }) != .lt) {
        // 0.15.2+: takeDelimiter returns null on EOF
        return reader.takeDelimiter('\n') catch |err| {
            return if (err == error.EndOfStream) null else null;
        };
    } else {
        // Pre-0.15.2: takeDelimiterExclusive throws EndOfStream on EOF
        return reader.takeDelimiterExclusive('\n') catch |err| switch (err) {
            error.EndOfStream => null,
            else => null,
        };
    }
}
```

### ArrayList/ObjectMap Changes

Zig 0.15.2 changed some managed collection APIs. Use the latest API patterns when writing new code.

---

## Compression in Zig 0.15

### The Problem

Zig 0.15 removed deflate/gzip compression from the standard library. Only decompression remains in `std.compress.flate`.

### The Solution

JN includes `comprezz.zig`, a ~1700-line port of Zig 0.14's deflate compression:

```
plugins/zig/gz/comprezz.zig
```

From the file header:
```zig
//! Gzip Compression Library for Zig 0.15
//!
//! This is a single-file implementation of gzip/deflate compression copied from
//! the Zig 0.14 standard library, as compression was removed in Zig 0.15.
```

### Usage

```zig
const comprezz = @import("comprezz.zig");

// Compression
var compressor = comprezz.deflate.compressor(.zlib, writer, .{});
try compressor.write(data);
try compressor.finish();

// Decompression (use stdlib)
const std = @import("std");
var decompressor = std.compress.flate.decompressor(reader);
const output = try decompressor.reader().readAllAlloc(allocator, max_size);
```

---

## Panic Troubleshooting

### Symptom: Compile-time TODO panic

```
error: TODO: ...
```

**Cause:** Using native x86 backend instead of LLVM.

**Fix:** Add `-fllvm` to your build command or `use_llvm = true` in `build.zig`.

### Symptom: Runtime panic in optimized builds

**Cause:** Possible undefined behavior or memory issues that debug builds catch.

**Fix:**
1. Test with `-O Debug` first
2. Check for buffer overflows, null pointer access
3. Verify all error unions are handled

### Symptom: Linking errors with C libraries

**Cause:** Missing library paths or incompatible ABIs.

**Fix:** Ensure correct `-I` (include) and `-L` (library) paths:
```bash
zig build-exe main.zig -fllvm \
  -I/path/to/include \
  -L/path/to/lib \
  -lopendal_c -lc
```

---

## OpenDAL Integration Notes

When building the OpenDAL plugin, additional flags are required:

```bash
zig build-exe main.zig -fllvm \
  -I../../../vendor/opendal/bindings/c/include \
  -L../../../vendor/opendal/bindings/c/target/debug \
  -lopendal_c -lc -femit-bin=opendal-test
```

Runtime requires library path:
```bash
LD_LIBRARY_PATH=../../../vendor/opendal/bindings/c/target/debug ./opendal-test
```

---

## Makefile Targets

The Makefile provides these Zig-related targets:

| Target | Description |
|--------|-------------|
| `make build` | Build all Zig components |
| `make test` | Run all Zig tests |
| `make zq` | Build ZQ filter engine only |
| `make zig-plugins` | Build all Zig plugins |
| `make zig-tools` | Build all Zig CLI tools |
| `make zig-libs-test` | Test shared libraries |
| `make fmt` | Format all Zig code |

Individual targets for parallel builds:
- `make plugin-csv`, `make plugin-json`, etc.
- `make tool-jn`, `make tool-jn-cat`, etc.

---

## Project Zig Structure

```
jn/
├── libs/zig/              # Shared libraries
│   ├── jn-core/           # Streaming I/O, JSON, errors
│   ├── jn-cli/            # Argument parsing
│   ├── jn-plugin/         # Plugin interface
│   ├── jn-address/        # Address parsing
│   ├── jn-profile/        # Profile resolution
│   └── jn-discovery/      # Plugin scanning
│
├── tools/zig/             # CLI tools
│   ├── jn/                # Main orchestrator
│   ├── jn-cat/            # Universal reader
│   ├── jn-put/            # Universal writer
│   └── ...                # Other tools
│
├── plugins/zig/           # Format plugins
│   ├── csv/               # CSV/TSV
│   ├── json/              # JSON arrays
│   ├── jsonl/             # NDJSON passthrough
│   ├── gz/                # Gzip (includes comprezz.zig)
│   ├── yaml/              # YAML
│   ├── toml/              # TOML
│   └── opendal/           # Protocol handler (experimental)
│
└── zq/                    # ZQ filter engine
    ├── src/main.zig
    └── build.zig
```

---

## Quick Reference

### Must-Know Facts

1. **Always use `-fllvm`** - Non-negotiable for Zig 0.15.x on x86
2. **Use `-O ReleaseFast`** - For production builds
3. **Test with `-O Debug`** - When debugging issues
4. **Compression needs `comprezz.zig`** - Stdlib only has decompression

### Common Build Pattern

```bash
zig build-exe main.zig -fllvm -O ReleaseFast -femit-bin=bin/my-tool
```

### Common Test Pattern

```bash
zig test src/root.zig -fllvm
```

---

## References

- `spec/opendal-analysis.md` - OpenDAL integration and `-fllvm` requirement
- `spec/zig-libraries-evaluation.md` - Library evaluation decisions
- `spec/log.md` - Implementation progress and notes
- `plugins/zig/gz/comprezz.zig` - Compression implementation
- `libs/zig/jn-core/src/reader.zig` - API compatibility patterns
