# Plugin Architecture Review: Pure CLI & Language-Agnostic Design

**Status:** Analysis Complete (Nov 2025)
**Goal:** Evaluate replacing module-level interface with pure CLI, multi-language support, and Rust integration for petabyte-scale processing.

---

## Executive Summary

**Current State:** JN already uses a **hybrid CLI architecture** - plugins are invoked as subprocesses (`uv run --script plugin.py --mode read`), but internally use Python module functions.

**Key Finding:** Transitioning to a pure CLI interface is straightforward and unlocks:
- Multi-language plugins (Rust, Go, C++)
- Better performance at petabyte scale
- Simplified plugin development

**Recommendation:** Implement a **phased approach**:
1. Standardize pure CLI contract
2. Create Rust-based high-performance plugins for hot paths
3. Keep Python for rapid prototyping and complex formats

---

## Current Architecture Analysis

### How Plugins Work Today

**Discovery** (fast, no execution):
```python
# Regex-parsed PEP 723 metadata
# /// script
# [tool.jn]
# matches = [".*\\.csv$"]
# ///
```

**Invocation** (always subprocess):
```bash
uv run --quiet --script csv_.py --mode read --delimiter "," < data.csv
```

**Data Contract**:
- Input: stdin (raw bytes or NDJSON)
- Output: stdout (NDJSON for read, format-specific for write)
- Errors: stderr
- Exit code: 0=success, non-zero=failure

### Plugins Examined (10 total)

| Plugin | Type | Lines | Dependencies | Key Patterns |
|--------|------|-------|--------------|--------------|
| csv_.py | Format | 278 | stdlib only | Auto-detect delimiter, streaming |
| json_.py | Format | 102 | stdlib only | NDJSON/array handling |
| xlsx_.py | Format | 192 | openpyxl | Binary stdin/stdout |
| http_.py | Protocol | 822 | requests | Profile resolution, streaming |
| duckdb_.py | Protocol | 541 | duckdb | Query params, profiles |
| jq_.py | Filter | 107 | stdlib only | Wraps jq CLI |
| gz_.py | Compression | 85 | stdlib only | Raw byte streaming |
| tail_shell.py | Shell | 133 | stdlib only | Subprocess wrapping |
| markdown_.py | Format | ~150 | stdlib | Table extraction |
| table_.py | Format | ~200 | tabulate | Pretty printing |

### Observations

1. **Already CLI-Based**: Framework invokes plugins via subprocess, never imports them
2. **Hybrid Internal Structure**: Plugins have `reads()`/`writes()` functions + `__main__` CLI wrapper
3. **No Framework Imports**: Plugins are fully standalone
4. **Config Via CLI Args**: `--mode`, `--delimiter`, `--limit`, etc.
5. **UV Handles Dependencies**: PEP 723 dependencies, isolated per-plugin

---

## Pure CLI Interface Proposal

### Current vs Proposed

**Current (Hybrid):**
```python
#!/usr/bin/env -S uv run --script
def reads(config=None):
    """Logic here"""

def writes(config=None):
    """Logic here"""

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode')
    # ... CLI wrapper calls reads/writes
```

**Proposed (Pure CLI):**
```python
#!/usr/bin/env -S uv run --script
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode')
    # ... All logic directly in CLI handler
```

### Standardized CLI Contract

```
INVOCATION:
  plugin --mode=read|write|raw [OPTIONS] [POSITIONAL_ARGS]

INPUTS:
  stdin:  Raw bytes (read/raw mode) or NDJSON lines (write mode)

OUTPUTS:
  stdout: NDJSON lines (read mode), format bytes (write mode), raw (raw mode)
  stderr: Human-readable errors

EXIT CODES:
  0: Success
  1: General error
  2: Invalid arguments

OPTIONS (common):
  --mode=read|write|raw   Required
  --limit=N               Limit output records
  --help                  Show help

OPTIONS (format-specific):
  --delimiter=CHAR        CSV delimiter
  --header=true|false     CSV header handling
  --indent=N              JSON indentation
  --sheet=NAME            XLSX sheet selector
```

### Language-Agnostic Discovery

**Current:** PEP 723 TOML in Python comments

**Proposed:** Sidecar JSON manifest OR self-describing `--jn-meta` flag

**Option A: Sidecar Manifest (csv_.json)**
```json
{
  "name": "csv",
  "matches": [".*\\.csv$", ".*\\.tsv$"],
  "role": "format",
  "modes": ["read", "write"],
  "dependencies": []
}
```

**Option B: Self-Describing Flag**
```bash
$ ./csv_plugin --jn-meta
{"name":"csv","matches":[".*\\.csv$"],"role":"format"}
```

**Recommendation:** Use sidecar manifests - faster (no execution), language-agnostic

---

## Multi-Language Plugin Support

### Language Suitability Matrix

| Language | Best For | Performance | Startup | Dependencies |
|----------|----------|-------------|---------|--------------|
| **Rust** | Hot paths, parsing | Excellent | <10ms | Static binary |
| **Go** | Network I/O, CLI tools | Very Good | <10ms | Static binary |
| **Python** | Complex formats, APIs | Good | 50-200ms (uv) | uv manages |
| **C++** | Existing libs (Excel) | Excellent | <10ms | System libs |
| **Shell** | Simple transforms | Variable | <5ms | System tools |

### Recommended Language by Plugin Type

| Plugin Type | Current | Recommended | Rationale |
|-------------|---------|-------------|-----------|
| CSV read | Python | **Rust** | Petabyte parsing, constant memory |
| CSV write | Python | **Rust** | High-throughput streaming |
| JSON read/write | Python | **Rust** | Simple, hot path |
| NDJSON passthrough | Python | **Rust** | Zero-copy potential |
| jq filter | Python→jq | **jq** (keep) | jq is already fast |
| XLSX read | Python | **Rust** (calamine) | calamine is faster than openpyxl |
| XLSX write | Python | Python (keep) | openpyxl is fine, less hot |
| HTTP fetch | Python | Python/Go | requests is fine, or Go for speed |
| DuckDB | Python | Python (keep) | duckdb-python is optimal |
| gzip | Python | **Rust** (flate2) | Streaming compression |

---

## Rust Integration Strategy

### Why Rust for Petabyte Scale?

1. **Memory Safety Without GC**: Constant memory, no GC pauses
2. **Zero-Copy Parsing**: Process data without allocations
3. **Predictable Performance**: No runtime overhead
4. **Excellent Libraries**: csv, serde_json, flate2, calamine
5. **Small Binaries**: <5MB static binaries

### Rust Plugin Template

```rust
// csv_plugin.rs
use std::io::{self, BufRead, Write};
use serde_json::json;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let mode = args.iter().find(|a| a.starts_with("--mode="))
        .map(|a| a.split('=').nth(1).unwrap())
        .unwrap_or("read");

    match mode {
        "read" => read_csv(),
        "write" => write_csv(),
        _ => eprintln!("Unknown mode: {}", mode),
    }
}

fn read_csv() {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut stdout = stdout.lock();

    let mut rdr = csv::Reader::from_reader(stdin.lock());
    let headers: Vec<String> = rdr.headers()
        .unwrap()
        .iter()
        .map(|s| s.to_string())
        .collect();

    for result in rdr.records() {
        let record = result.unwrap();
        let obj: serde_json::Map<String, serde_json::Value> = headers
            .iter()
            .zip(record.iter())
            .map(|(k, v)| (k.clone(), json!(v)))
            .collect();

        serde_json::to_writer(&mut stdout, &obj).unwrap();
        stdout.write_all(b"\n").unwrap();
    }
}
```

### Build & Distribution

```toml
# Cargo.toml
[package]
name = "jn-plugins-rs"
version = "0.1.0"

[[bin]]
name = "csv_"
path = "src/csv.rs"

[[bin]]
name = "json_"
path = "src/json.rs"

[dependencies]
csv = "1.3"
serde_json = "1.0"
flate2 = "1.0"
calamine = "0.24"  # Excel reading
```

**Distribution Options:**
1. **Pre-built binaries**: Ship in `jn_home/plugins/bin/`
2. **Build on install**: `cargo build --release` during `pip install jn`
3. **Optional package**: `pip install jn[rust-plugins]`

---

## Performance Projections

### Petabyte Processing Scenario

**Workload:** 1 PB CSV data (1000 x 1TB files), extract subset

**Python Plugin:**
```
Parse rate: ~50 MB/s per process
Total time: 1 PB / 50 MB/s = 20,000,000 seconds = 231 days
With 100 parallel: ~2.3 days
Memory per process: ~100 MB (Python overhead)
```

**Rust Plugin:**
```
Parse rate: ~500 MB/s per process (10x faster)
Total time: 1 PB / 500 MB/s = 2,000,000 seconds = 23 days
With 100 parallel: ~5.5 hours
Memory per process: ~10 MB (no runtime)
```

### Benchmarks (Projected)

| Operation | Python | Rust | Speedup |
|-----------|--------|------|---------|
| CSV parse (1GB) | 20s | 2s | 10x |
| JSON parse (1GB) | 15s | 1.5s | 10x |
| gzip decompress (1GB) | 8s | 3s | 2.7x |
| XLSX parse (100MB) | 30s | 5s | 6x |
| Process startup | 50-200ms | <10ms | 10-20x |

---

## Implementation Phases

### Phase 1: Standardize CLI Contract (1-2 weeks)

1. Document standard CLI contract (see above)
2. Add `--jn-meta` flag to existing plugins
3. Create sidecar manifest generator
4. Update discovery to read manifests

**Changes:**
- `src/jn/plugins/discovery.py`: Support JSON manifests
- `jn_home/plugins/*/`: Add .json manifests
- No breaking changes to existing plugins

### Phase 2: Rust Core Plugins (2-4 weeks)

Priority order:
1. `csv_.rs` - Highest impact, most used
2. `json_.rs` - Simple, foundational
3. `gz_.rs` - Compression hot path
4. `ndjson_.rs` - Passthrough optimization

**Deliverables:**
- `jn-plugins-rs` crate
- Build integration in Makefile
- Benchmark suite

### Phase 3: Language-Agnostic Discovery (1 week)

1. Support any executable with matching manifest
2. Discovery order: .json manifest → PEP 723 fallback
3. Update plugin list/info commands

### Phase 4: Performance Optimization (ongoing)

1. Profile real workloads
2. Replace Python plugins with Rust as needed
3. Add SIMD optimizations for parsing
4. Memory-mapped I/O for large files

---

## What Parts of JN Should Be Rust?

### Current Python Components

| Component | LOC | Rust Benefit | Priority |
|-----------|-----|--------------|----------|
| CLI entry (click) | 500 | Low | Keep Python |
| Plugin discovery | 200 | Low | Keep Python |
| Address parsing | 400 | Low | Keep Python |
| Profile resolution | 600 | Low | Keep Python |
| Pipeline orchestration | 300 | Low | Keep Python |
| **CSV plugin** | 280 | **High** | **Rust** |
| **JSON plugin** | 100 | **High** | **Rust** |
| **gzip plugin** | 85 | **Medium** | **Rust** |
| HTTP plugin | 820 | Low | Keep Python |
| DuckDB plugin | 540 | Low | Keep Python |

### Recommendation

**Rust plugins only.** Keep framework in Python because:
1. Click provides good CLI ergonomics
2. Framework is not in hot path
3. Python is easier to modify for agent tasks
4. Plugin subprocess isolation means language doesn't matter for framework

---

## Risk Analysis

### Risks of Multi-Language

| Risk | Mitigation |
|------|------------|
| Build complexity | Cargo in Makefile, CI builds |
| Cross-platform binaries | Cross-compilation, GitHub Actions |
| Debugging difficulty | Structured logging, --debug flag |
| Contributor friction | Keep Python as default, Rust optional |

### Risks of Pure CLI

| Risk | Mitigation |
|------|------------|
| Testing harder | Integration tests, fixtures |
| Config validation | Schema in manifest, --validate flag |
| Startup overhead | Pre-built binaries, warm cache |

---

## Conclusion

JN's architecture is well-suited for multi-language plugins. The subprocess model already provides language isolation. Key recommendations:

1. **Standardize CLI contract** - Formal spec for plugin interface
2. **Add sidecar manifests** - Language-agnostic discovery
3. **Build Rust core plugins** - CSV, JSON, gzip for 10x performance
4. **Keep Python framework** - Not in hot path, good for iteration

For petabyte-scale processing, the combination of:
- Rust plugins for parsing (10x speedup)
- Python framework for orchestration (flexibility)
- Unix pipes for backpressure (constant memory)

...provides an excellent architecture that scales to arbitrary data sizes.
