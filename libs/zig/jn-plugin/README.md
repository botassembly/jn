# jn-plugin - Zig Plugin Library for JN

A library for building high-performance JN plugins in Zig.

## Features

- Core types: `Plugin`, `Config`, `Role`, `Mode`
- CLI argument parsing (`--mode=read|write`, `--jn-meta`)
- Manifest generation for plugin discovery
- Zig 0.15.2 compatible (Writergate I/O API)

## Quick Start

See `examples/jsonl/main.zig` for a complete standalone plugin example.

```zig
const std = @import("std");

const plugin = .{
    .name = "myformat",
    .version = "0.1.0",
    .matches = &[_][]const u8{".*\\.myformat$"},
    .role = "format",
    .modes = &[_][]const u8{ "read", "write" },
};

pub fn main() !void {
    // Parse args, handle --jn-meta, dispatch to read/write mode
    // ...
}
```

## Building

```bash
# Run library tests
zig test src/lib.zig -fllvm

# Build JSONL example plugin
zig build-exe examples/jsonl/main.zig -fllvm -O ReleaseFast -femit-bin=zig-out/bin/jsonl

# Test the plugin
./zig-out/bin/jsonl --jn-meta
echo '{"name":"test"}' | ./zig-out/bin/jsonl --mode=read
```

## Plugin Protocol

Plugins communicate via:
- **stdin/stdout**: NDJSON streaming
- **--mode=read|write**: Operation mode
- **--jn-meta**: Output plugin manifest as JSON

## Status

Sprint 06 - Initial implementation complete:
- [x] Core types (Plugin, Config, Role, Mode)
- [x] CLI argument parsing
- [x] Manifest generation
- [x] JSONL example plugin working
- [ ] Full library integration with build system (pending Zig 0.15.2 module syntax)
