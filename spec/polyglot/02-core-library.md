# JN Plugin Core Library Design

**Goal:** Extract common abstractions into reusable libraries for Python and Rust plugin development.

---

## Identified Boilerplate (from 10 plugins)

### 1. CLI Argument Parsing
Every plugin duplicates:
```python
parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=["read", "write", "raw"], required=True)
parser.add_argument("--limit", type=int)
# ... format-specific args
args = parser.parse_args()
```

### 2. NDJSON Output Loop
Every reader plugin:
```python
for record in reads(config):
    print(json.dumps(record), flush=True)
```

### 3. NDJSON Input Loop
Every writer plugin:
```python
for line in sys.stdin:
    line = line.strip()
    if line:
        records.append(json.loads(line))
```

### 4. Error Handling
```python
try:
    # ... work ...
except BrokenPipeError:
    os._exit(0)  # Graceful SIGPIPE
except Exception as e:
    sys.stderr.write(f"Error: {e}\n")
    sys.exit(1)
```

### 5. Binary I/O
```python
# Read binary
data = sys.stdin.buffer.read()
# Write binary
sys.stdout.buffer.write(output)
sys.stdout.buffer.flush()
```

---

## Python Core Library: `jn_plugin`

### Installation
```toml
# In plugin's PEP 723 header
# dependencies = ["jn-plugin-core"]
```

### API Design

```python
# jn_plugin/__init__.py

from dataclasses import dataclass
from typing import Iterator, Callable, Any
import json
import sys
import os

@dataclass
class PluginConfig:
    """Base configuration available to all plugins."""
    mode: str  # "read", "write", "raw"
    limit: int | None = None
    # Additional fields populated from CLI args

class Plugin:
    """Base class for JN plugins with common abstractions."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._read_fn: Callable | None = None
        self._write_fn: Callable | None = None
        self._raw_fn: Callable | None = None
        self._args: list[tuple] = []  # Custom arguments

    def arg(self, *args, **kwargs):
        """Add custom CLI argument."""
        self._args.append((args, kwargs))
        return self

    def reader(self, fn: Callable[[dict], Iterator[dict]]):
        """Register read function."""
        self._read_fn = fn
        return fn

    def writer(self, fn: Callable[[dict], None]):
        """Register write function."""
        self._write_fn = fn
        return fn

    def raw(self, fn: Callable[[dict], None]):
        """Register raw mode function."""
        self._raw_fn = fn
        return fn

    def run(self):
        """Parse args and execute appropriate mode."""
        import argparse

        parser = argparse.ArgumentParser(description=self.description)
        parser.add_argument("--mode", choices=["read", "write", "raw"], required=True)
        parser.add_argument("--limit", type=int, help="Limit output records")
        parser.add_argument("--jn-meta", action="store_true", help="Output plugin metadata")

        # Add custom arguments
        for args, kwargs in self._args:
            parser.add_argument(*args, **kwargs)

        parsed, remaining = parser.parse_known_args()

        # Handle metadata request
        if parsed.jn_meta:
            self._output_metadata()
            return

        # Build config from parsed args
        config = vars(parsed)

        try:
            if parsed.mode == "read" and self._read_fn:
                self._run_reader(config)
            elif parsed.mode == "write" and self._write_fn:
                self._run_writer(config)
            elif parsed.mode == "raw" and self._raw_fn:
                self._raw_fn(config)
            else:
                sys.stderr.write(f"Mode '{parsed.mode}' not supported\n")
                sys.exit(1)
        except BrokenPipeError:
            os._exit(0)
        except KeyboardInterrupt:
            os._exit(0)
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            sys.exit(1)

    def _run_reader(self, config: dict):
        """Execute reader with NDJSON output and limit support."""
        limit = config.get("limit")
        count = 0

        for record in self._read_fn(config):
            print(json.dumps(record), flush=True)
            count += 1
            if limit and count >= limit:
                break

    def _run_writer(self, config: dict):
        """Execute writer."""
        self._write_fn(config)

    def _output_metadata(self):
        """Output plugin metadata as JSON."""
        meta = {
            "name": self.name,
            "modes": [],
        }
        if self._read_fn:
            meta["modes"].append("read")
        if self._write_fn:
            meta["modes"].append("write")
        if self._raw_fn:
            meta["modes"].append("raw")
        print(json.dumps(meta))


# Convenience functions for I/O

def read_ndjson() -> Iterator[dict]:
    """Read NDJSON lines from stdin."""
    for line in sys.stdin:
        line = line.strip()
        if line:
            yield json.loads(line)

def read_ndjson_all() -> list[dict]:
    """Read all NDJSON lines into list."""
    return list(read_ndjson())

def read_binary() -> bytes:
    """Read binary data from stdin."""
    return sys.stdin.buffer.read()

def read_text() -> str:
    """Read all text from stdin."""
    return sys.stdin.read()

def write_ndjson(record: dict):
    """Write single NDJSON record to stdout."""
    print(json.dumps(record), flush=True)

def write_binary(data: bytes):
    """Write binary data to stdout."""
    try:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    except BrokenPipeError:
        os._exit(0)

def write_text(text: str):
    """Write text to stdout."""
    sys.stdout.write(text)
```

### Example: CSV Plugin Using Core Library

**Before (current):** 278 lines

**After (with core library):** ~80 lines

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["jn-plugin-core"]
# [tool.jn]
# matches = [".*\\.csv$", ".*\\.tsv$"]
# ///
"""CSV format plugin."""

import csv
import sys
from jn_plugin import Plugin, read_ndjson_all

plugin = Plugin("csv", "Parse CSV/TSV files")

# Define custom arguments
plugin.arg("--delimiter", default="auto", help="Field delimiter")
plugin.arg("--skip-rows", type=int, default=0, help="Rows to skip")
plugin.arg("--no-header", dest="header", action="store_false")

@plugin.reader
def reads(config):
    """Read CSV from stdin, yield records."""
    delimiter = config.get("delimiter", "auto")
    skip_rows = config.get("skip_rows", 0)

    # Auto-detect delimiter if needed
    if delimiter == "auto":
        delimiter = _detect_delimiter()

    # Skip rows
    for _ in range(skip_rows):
        next(sys.stdin, None)

    reader = csv.DictReader(sys.stdin, delimiter=delimiter)
    yield from reader

@plugin.writer
def writes(config):
    """Write NDJSON to CSV."""
    delimiter = config.get("delimiter", ",")
    header = config.get("header", True)

    records = read_ndjson_all()
    if not records:
        return

    # Get all keys
    all_keys = []
    seen = set()
    for record in records:
        for key in record:
            if key not in seen:
                all_keys.append(key)
                seen.add(key)

    writer = csv.DictWriter(sys.stdout, fieldnames=all_keys, delimiter=delimiter)
    if header:
        writer.writeheader()
    writer.writerows(records)

def _detect_delimiter():
    # ... delimiter detection logic ...
    return ","

if __name__ == "__main__":
    plugin.run()
```

---

## Rust Core Library: `jn_plugin`

### Cargo.toml
```toml
[package]
name = "jn-plugin"
version = "0.1.0"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
clap = { version = "4.0", features = ["derive"] }
```

### API Design

```rust
// src/lib.rs

use std::io::{self, BufRead, BufWriter, Write};
use serde_json::Value;

/// Plugin mode
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Mode {
    Read,
    Write,
    Raw,
}

/// Base plugin configuration
pub struct Config {
    pub mode: Mode,
    pub limit: Option<usize>,
    pub args: std::collections::HashMap<String, String>,
}

/// Read NDJSON records from stdin
pub fn read_ndjson() -> impl Iterator<Item = Value> {
    let stdin = io::stdin();
    stdin.lock().lines().filter_map(|line| {
        line.ok().and_then(|s| {
            let trimmed = s.trim();
            if trimmed.is_empty() {
                None
            } else {
                serde_json::from_str(trimmed).ok()
            }
        })
    })
}

/// Read all NDJSON into Vec
pub fn read_ndjson_all() -> Vec<Value> {
    read_ndjson().collect()
}

/// Read binary from stdin
pub fn read_binary() -> io::Result<Vec<u8>> {
    let mut buffer = Vec::new();
    io::stdin().lock().read_to_end(&mut buffer)?;
    Ok(buffer)
}

/// Read text from stdin
pub fn read_text() -> io::Result<String> {
    let mut buffer = String::new();
    io::stdin().lock().read_to_string(&mut buffer)?;
    Ok(buffer)
}

/// Write single NDJSON record (with newline and flush)
pub fn write_ndjson(record: &Value) -> io::Result<()> {
    let stdout = io::stdout();
    let mut handle = stdout.lock();
    serde_json::to_writer(&mut handle, record)?;
    writeln!(handle)?;
    handle.flush()
}

/// Buffered NDJSON writer for high throughput
pub struct NdjsonWriter {
    writer: BufWriter<io::Stdout>,
}

impl NdjsonWriter {
    pub fn new() -> Self {
        Self {
            writer: BufWriter::with_capacity(64 * 1024, io::stdout()),
        }
    }

    pub fn write(&mut self, record: &Value) -> io::Result<()> {
        serde_json::to_writer(&mut self.writer, record)?;
        self.writer.write_all(b"\n")
    }

    pub fn flush(&mut self) -> io::Result<()> {
        self.writer.flush()
    }
}

impl Drop for NdjsonWriter {
    fn drop(&mut self) {
        let _ = self.flush();
    }
}

/// Write binary to stdout
pub fn write_binary(data: &[u8]) -> io::Result<()> {
    let stdout = io::stdout();
    let mut handle = stdout.lock();
    handle.write_all(data)?;
    handle.flush()
}

/// Macro for defining a plugin with common boilerplate
#[macro_export]
macro_rules! plugin {
    (
        name: $name:expr,
        $(reader: $reader:expr,)?
        $(writer: $writer:expr,)?
        $(raw: $raw:expr,)?
        $(args: [$($arg:expr),* $(,)?],)?
    ) => {
        fn main() {
            use clap::Parser;
            use jn_plugin::{Mode, Config};

            #[derive(Parser)]
            #[command(name = $name)]
            struct Args {
                #[arg(long, value_parser = parse_mode)]
                mode: Mode,

                #[arg(long)]
                limit: Option<usize>,

                $($($arg)*)?
            }

            fn parse_mode(s: &str) -> Result<Mode, String> {
                match s {
                    "read" => Ok(Mode::Read),
                    "write" => Ok(Mode::Write),
                    "raw" => Ok(Mode::Raw),
                    _ => Err(format!("Invalid mode: {}", s)),
                }
            }

            let args = Args::parse();

            let result = match args.mode {
                $(Mode::Read => $reader(&args),)?
                $(Mode::Write => $writer(&args),)?
                $(Mode::Raw => $raw(&args),)?
                #[allow(unreachable_patterns)]
                _ => {
                    eprintln!("Mode not supported");
                    std::process::exit(1);
                }
            };

            if let Err(e) = result {
                // Check for broken pipe
                if e.kind() == std::io::ErrorKind::BrokenPipe {
                    std::process::exit(0);
                }
                eprintln!("Error: {}", e);
                std::process::exit(1);
            }
        }
    };
}
```

### Example: CSV Plugin in Rust

```rust
// csv_plugin.rs

use std::io::{self, BufRead, Write};
use jn_plugin::{NdjsonWriter, read_ndjson_all};
use serde_json::{json, Map, Value};

jn_plugin::plugin! {
    name: "csv",
    reader: read_csv,
    writer: write_csv,
    args: [
        #[arg(long, default_value = ",")]
        delimiter: char,

        #[arg(long, default_value = "0")]
        skip_rows: usize,

        #[arg(long)]
        no_header: bool,
    ],
}

fn read_csv(args: &Args) -> io::Result<()> {
    let stdin = io::stdin();
    let mut lines = stdin.lock().lines().skip(args.skip_rows);

    // Read header
    let header: Vec<String> = match lines.next() {
        Some(Ok(line)) => line.split(args.delimiter).map(String::from).collect(),
        _ => return Ok(()),
    };

    let mut writer = NdjsonWriter::new();
    let mut count = 0;

    for line in lines {
        let line = line?;
        let values: Vec<&str> = line.split(args.delimiter).collect();

        let mut record = Map::new();
        for (i, key) in header.iter().enumerate() {
            let value = values.get(i).unwrap_or(&"");
            record.insert(key.clone(), json!(value));
        }

        writer.write(&Value::Object(record))?;

        count += 1;
        if let Some(limit) = args.limit {
            if count >= limit {
                break;
            }
        }
    }

    Ok(())
}

fn write_csv(args: &Args) -> io::Result<()> {
    let records = read_ndjson_all();
    if records.is_empty() {
        return Ok(());
    }

    // Collect all keys
    let mut keys: Vec<String> = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for record in &records {
        if let Value::Object(map) = record {
            for key in map.keys() {
                if !seen.contains(key) {
                    keys.push(key.clone());
                    seen.insert(key.clone());
                }
            }
        }
    }

    let stdout = io::stdout();
    let mut out = stdout.lock();

    // Write header
    if !args.no_header {
        writeln!(out, "{}", keys.join(&args.delimiter.to_string()))?;
    }

    // Write rows
    for record in &records {
        if let Value::Object(map) = record {
            let row: Vec<String> = keys.iter()
                .map(|k| map.get(k).and_then(|v| v.as_str()).unwrap_or("").to_string())
                .collect();
            writeln!(out, "{}", row.join(&args.delimiter.to_string()))?;
        }
    }

    Ok(())
}
```

---

## Comparison: Lines of Code

| Plugin | Current Python | With Core Lib | Rust |
|--------|---------------|---------------|------|
| csv_.py | 278 | ~80 | ~100 |
| json_.py | 102 | ~40 | ~60 |
| yaml_.py | 103 | ~50 | ~70 |
| toml_.py | 148 | ~60 | ~80 |
| gz_.py | 85 | ~30 | ~40 |

**Average reduction: 60-70% less boilerplate**

---

## Shared Abstractions Summary

### Python `jn_plugin`
- `Plugin` class with decorator-based registration
- `read_ndjson()`, `read_binary()`, `read_text()`
- `write_ndjson()`, `write_binary()`
- Automatic SIGPIPE/KeyboardInterrupt handling
- Automatic `--limit` enforcement
- `--jn-meta` for introspection

### Rust `jn_plugin`
- `plugin!` macro for boilerplate
- `read_ndjson()`, `read_binary()`, `read_text()`
- `NdjsonWriter` for buffered high-throughput output
- `write_ndjson()`, `write_binary()`
- Automatic broken pipe handling
- clap integration for args

---

## Implementation Plan

### Phase 1: Python Core Library
1. Create `jn-plugin-core` package
2. Implement `Plugin` class and I/O helpers
3. Migrate one plugin (csv_) as proof of concept
4. Add tests

### Phase 2: Rust Core Library
1. Create `jn-plugin` crate
2. Implement macros and I/O helpers
3. Build CSV plugin as proof of concept
4. Benchmark vs Python

### Phase 3: Migration
1. Migrate Python plugins to use core library
2. Build high-performance Rust versions of hot-path plugins
3. Update documentation

---

## Benefits

1. **Reduced Boilerplate**: 60-70% less code per plugin
2. **Consistent Behavior**: All plugins handle errors, limits, SIGPIPE identically
3. **Easier Onboarding**: Write plugin logic only, core handles infrastructure
4. **Multi-Language**: Same abstractions in Python and Rust
5. **Testability**: Core library well-tested, plugins test only logic
6. **Performance**: Rust plugins using same interface as Python
