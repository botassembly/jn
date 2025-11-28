# Language Comparison for JN Plugins

**Core insight:** The CLI contract is language-agnostic. Any language that produces an executable works.

```
stdin (bytes/NDJSON) → plugin executable → stdout (NDJSON/bytes)
```

---

## Language Options

### Tier 1: Recommended

| Language | Best For | Startup | Throughput | Cross-compile | Learning Curve |
|----------|----------|---------|------------|---------------|----------------|
| **Rust** | Parsing, transforms | <5ms | Excellent | Good (cross) | Steep |
| **Go** | Network, protocols | <5ms | Very Good | Excellent | Gentle |
| **C** | Wrapping C libs | <1ms | Excellent | Manual | Moderate |

### Tier 2: Viable

| Language | Best For | Startup | Throughput | Cross-compile | Learning Curve |
|----------|----------|---------|------------|---------------|----------------|
| **Zig** | C interop, SIMD | <1ms | Excellent | Excellent | Moderate |
| **Nim** | Python devs | <5ms | Very Good | Good | Gentle |
| **C++** | Existing libs | <1ms | Excellent | Manual | Steep |

### Tier 3: Special Cases

| Language | Best For | Startup | Throughput | Cross-compile | Learning Curve |
|----------|----------|---------|------------|---------------|----------------|
| **Shell** | CLI wrappers | <10ms | N/A (wrapper) | Native | Trivial |
| **Python+Nuitka** | Existing Python | ~50ms | Good | Limited | None |
| **Java+GraalVM** | JVM ecosystem | <10ms | Very Good | Moderate | Moderate |

---

## When to Use Each Language

### Rust
**Best for:** Hot-path format parsing (CSV, JSON, XML)

```rust
// Strengths
- Zero-copy parsing (csv, simd-json)
- Predictable memory (no GC pauses)
- Excellent error handling
- Rich ecosystem (serde, clap)

// Weaknesses
- Slower compilation
- Steeper learning curve
- More verbose than Go
```

**Example plugins:** `csv_`, `json_`, `xml_`, `gz_`

### Go
**Best for:** Network protocols, concurrent I/O

```go
// Strengths
- Trivial cross-compilation (GOOS/GOARCH)
- Excellent stdlib (net/http, encoding/json)
- Fast compilation (<1s for plugins)
- Goroutines for concurrent I/O
- Simple deployment (single static binary)

// Weaknesses
- GC can cause latency spikes
- Less control than Rust
- Larger binaries (~5-10MB)
```

**Example plugins:** `http_`, `s3_`, `websocket_`

### C
**Best for:** Wrapping existing C libraries

```c
// Strengths
- Maximum performance
- Direct access to system libs
- Smallest binaries
- Fastest startup

// Weaknesses
- Memory safety issues
- Manual memory management
- No standard package manager
```

**Example plugins:** Wrapping `libcsv`, `libxml2`, `zlib`

### Zig
**Best for:** C interop with safety, SIMD

```zig
// Strengths
- Seamless C interop (import C headers directly)
- No hidden allocations
- SIMD primitives built-in
- Cross-compile to 30+ targets

// Weaknesses
- Pre-1.0, API unstable
- Smaller ecosystem
```

**Example plugins:** High-performance CSV with SIMD, wrapping C libs safely

### Shell (Bash/Fish/Zsh)
**Best for:** Thin wrappers around existing CLIs

```bash
#!/bin/bash
# Just wrap an existing tool
case "$1" in
  --jn-meta) echo '{"name":"wrapper","matches":["..."]}' ;;
  --mode=read) some-cli --json "$2" ;;
esac
```

**Example plugins:** Wrapping `jq`, `yq`, `csvtool`, `xmllint`

---

## Go vs Rust: Detailed Comparison

### Performance

| Metric | Rust | Go |
|--------|------|-----|
| CSV parse (1GB) | ~2s | ~3-4s |
| JSON parse (1GB) | ~1.5s | ~2-3s |
| HTTP fetch | Same | Same |
| Memory (streaming) | ~10MB | ~20-30MB |
| Binary size | ~2-5MB | ~5-10MB |

**Verdict:** Rust is ~30-50% faster for parsing. Go is "fast enough" for most use cases.

### Development Speed

| Metric | Rust | Go |
|--------|------|-----|
| Compile time | 10-30s | <1s |
| Learning curve | Weeks | Days |
| Boilerplate | More | Less |
| Debugging | Harder | Easier |

**Verdict:** Go is 5-10x faster to develop.

### Cross-Compilation

```bash
# Go: One-liner
GOOS=linux GOARCH=arm64 go build -o plugin_linux_arm64

# Rust: Requires toolchain setup
rustup target add aarch64-unknown-linux-gnu
cargo build --target aarch64-unknown-linux-gnu
# Often needs cross or docker
```

**Verdict:** Go wins significantly.

### Recommendation

| Plugin Type | Recommended | Rationale |
|-------------|-------------|-----------|
| Format parsing (csv, json) | **Rust** | Hot path, 10x improvement matters |
| Protocols (http, s3) | **Go** | Network I/O, easier async |
| Compression (gz, zstd) | **Rust** | CPU-bound, benefits from optimization |
| CLI wrappers | **Shell** | Simplest, no compilation |
| C library wrappers | **C** or **Zig** | Direct interop |

---

## Example: Same Plugin in Different Languages

### Go Version (`csv_/main.go`)

```go
package main

import (
    "encoding/csv"
    "encoding/json"
    "flag"
    "fmt"
    "io"
    "os"
)

type Meta struct {
    Name    string   `json:"name"`
    Matches []string `json:"matches"`
    Modes   []string `json:"modes"`
}

func main() {
    mode := flag.String("mode", "", "read|write")
    jnMeta := flag.Bool("jn-meta", false, "output metadata")
    limit := flag.Int("limit", 0, "limit records")
    flag.Parse()

    if *jnMeta {
        meta := Meta{
            Name:    "csv",
            Matches: []string{`.*\.csv$`, `.*\.tsv$`},
            Modes:   []string{"read", "write"},
        }
        json.NewEncoder(os.Stdout).Encode(meta)
        return
    }

    switch *mode {
    case "read":
        readCSV(*limit)
    case "write":
        writeCSV()
    default:
        fmt.Fprintln(os.Stderr, "Error: --mode required")
        os.Exit(1)
    }
}

func readCSV(limit int) {
    reader := csv.NewReader(os.Stdin)
    headers, _ := reader.Read()

    count := 0
    for {
        record, err := reader.Read()
        if err == io.EOF {
            break
        }

        row := make(map[string]string)
        for i, h := range headers {
            if i < len(record) {
                row[h] = record[i]
            }
        }

        json.NewEncoder(os.Stdout).Encode(row)

        count++
        if limit > 0 && count >= limit {
            break
        }
    }
}

func writeCSV() {
    // ... similar implementation
}
```

**Build:** `go build -o csv_ .`
**Size:** ~5MB
**Compile time:** <1s

### Shell Wrapper (`jq_/jq_.sh`)

```bash
#!/bin/bash
set -e

case "$1" in
    --jn-meta)
        echo '{"name":"jq","matches":[],"modes":["filter"]}'
        exit 0
        ;;
    --mode)
        shift
        if [ "$1" = "filter" ]; then
            shift
            exec jq -c "$@"
        fi
        ;;
esac

echo "Error: invalid arguments" >&2
exit 1
```

**Size:** ~500 bytes
**No compilation needed**

### Zig Version (`gz_/main.zig`)

```zig
const std = @import("std");
const zlib = @cImport(@cInclude("zlib.h"));

pub fn main() !void {
    var args = std.process.args();
    _ = args.next(); // skip program name

    while (args.next()) |arg| {
        if (std.mem.eql(u8, arg, "--jn-meta")) {
            try std.io.getStdOut().writeAll(
                \\{"name":"gz","matches":[".*\\.gz$"],"modes":["raw"]}
            );
            return;
        }
        if (std.mem.eql(u8, arg, "--mode")) {
            // ... handle modes
        }
    }
}
```

**Build:** `zig build-exe main.zig -O ReleaseFast`
**Size:** ~100KB (tiny!)
**C interop:** Direct `@cImport`

---

## Practical Recommendations

### For JN Core Plugins

```
Format plugins (hot path):     Rust
  csv_, json_, xml_, yaml_     - Maximum throughput matters

Compression (CPU-bound):       Rust
  gz_, zstd_, lz4_             - Benefits from optimization

Protocols (I/O-bound):         Go
  http_, s3_, gcs_             - Easier async, great stdlib

Database (bindings):           Keep Python or Go
  duckdb_, sqlite_             - Native bindings available

CLI wrappers:                  Shell
  jq_, yq_, xmllint_           - Simplest solution
```

### For User Plugins

**Start with Shell** for prototyping:
```bash
#!/bin/bash
mytool --format=json "$@"
```

**Graduate to Go** when you need:
- Better error handling
- Cross-platform distribution
- Performance

**Use Rust** only when:
- Processing TB+ of data
- Every millisecond matters
- You already know Rust

---

## Summary

| Question | Answer |
|----------|--------|
| Can any language be used? | **Yes** - any executable that speaks the CLI contract |
| Best language overall? | **Depends on use case** - no single winner |
| Best for parsing? | **Rust** - zero-copy, SIMD, predictable |
| Best for protocols? | **Go** - stdlib, easy async, fast compile |
| Best for wrappers? | **Shell** - zero complexity |
| Best for C libs? | **C** or **Zig** - direct interop |

The CLI contract is the great equalizer - use whatever language fits the job.
