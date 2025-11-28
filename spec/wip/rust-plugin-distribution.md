# Rust Plugin Development & Distribution

**Goal:** Enable Rust plugin development that's as easy as Python, with cross-platform bundled plugins.

---

## Part 1: User-Written Rust Plugins

### Discovery: Sidecar Manifests

Since we can't parse PEP 723 from binaries, use JSON sidecar files:

```
jn_home/plugins/
├── formats/
│   ├── my_plugin           # Compiled binary (no extension on Unix)
│   ├── my_plugin.exe       # Windows variant
│   └── my_plugin.json      # Sidecar manifest (required)
```

**Manifest format (`my_plugin.json`):**
```json
{
  "name": "my_plugin",
  "version": "0.1.0",
  "matches": [".*\\.myformat$"],
  "role": "format",
  "modes": ["read", "write"],
  "description": "My custom format plugin",
  "binary": {
    "linux-x86_64": "my_plugin",
    "linux-aarch64": "my_plugin",
    "darwin-x86_64": "my_plugin",
    "darwin-aarch64": "my_plugin",
    "windows-x86_64": "my_plugin.exe"
  }
}
```

### Simple Case: Single Binary

For users who just want to drop in a binary:
```json
{
  "name": "my_plugin",
  "matches": [".*\\.myformat$"],
  "modes": ["read", "write"]
}
```

Discovery logic: Look for `my_plugin` or `my_plugin.exe` next to `my_plugin.json`.

### User Development Workflow

**Option A: Compile locally, copy binary**
```bash
# In user's project
cargo build --release
cp target/release/my_plugin ~/.jn/plugins/formats/
cp my_plugin.json ~/.jn/plugins/formats/

# Test
jn cat test.myformat
```

**Option B: Use `jn plugin build` helper**
```bash
# In plugin directory with Cargo.toml
jn plugin build .
# Compiles and installs to ~/.jn/plugins/formats/my_plugin + .json
```

---

## Part 2: Bundled Core Plugins

### Repository Structure

```
jn-plugins-rs/
├── Cargo.toml              # Workspace
├── crates/
│   ├── jn-plugin/          # Core library (shared)
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── io.rs       # read_ndjson, write_ndjson, etc.
│   │       ├── cli.rs      # CLI parsing helpers
│   │       └── error.rs    # Error handling
│   │
│   ├── csv/                # CSV plugin
│   │   ├── Cargo.toml
│   │   ├── src/main.rs
│   │   └── plugin.json     # Manifest template
│   │
│   ├── json/               # JSON plugin
│   │   ├── Cargo.toml
│   │   ├── src/main.rs
│   │   └── plugin.json
│   │
│   ├── gz/                 # Gzip plugin
│   │   ├── Cargo.toml
│   │   ├── src/main.rs
│   │   └── plugin.json
│   │
│   └── ndjson/             # NDJSON passthrough (zero-copy)
│       ├── Cargo.toml
│       ├── src/main.rs
│       └── plugin.json
│
├── build.rs                # Build script
├── Makefile                # Cross-compilation targets
└── .github/
    └── workflows/
        └── release.yml     # CI/CD for multi-platform builds
```

### Workspace Cargo.toml

```toml
[workspace]
resolver = "2"
members = [
    "crates/jn-plugin",
    "crates/csv",
    "crates/json",
    "crates/gz",
    "crates/ndjson",
]

[workspace.package]
version = "0.1.0"
edition = "2021"
license = "MIT"
repository = "https://github.com/botassembly/jn-plugins-rs"

[workspace.dependencies]
jn-plugin = { path = "crates/jn-plugin" }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
clap = { version = "4.0", features = ["derive"] }
csv = "1.3"
flate2 = "1.0"

[profile.release]
lto = true
codegen-units = 1
strip = true
panic = "abort"
```

### Core Library (`jn-plugin/src/lib.rs`)

```rust
//! JN Plugin Core Library
//!
//! Provides common abstractions for Rust-based JN plugins.

pub mod io;
pub mod cli;
pub mod error;

pub use io::*;
pub use cli::*;
pub use error::*;

// Re-export commonly used types
pub use serde_json::{json, Value, Map};
```

### I/O Module (`jn-plugin/src/io.rs`)

```rust
use std::io::{self, BufRead, BufWriter, Write, Read};
use serde_json::Value;

/// Streaming NDJSON reader
pub struct NdjsonReader<R: BufRead> {
    reader: R,
    line_buf: String,
}

impl<R: BufRead> NdjsonReader<R> {
    pub fn new(reader: R) -> Self {
        Self {
            reader,
            line_buf: String::with_capacity(4096),
        }
    }

    pub fn from_stdin() -> NdjsonReader<io::StdinLock<'static>> {
        // Use static lifetime trick for convenience
        let stdin = Box::leak(Box::new(io::stdin()));
        NdjsonReader::new(stdin.lock())
    }
}

impl<R: BufRead> Iterator for NdjsonReader<R> {
    type Item = io::Result<Value>;

    fn next(&mut self) -> Option<Self::Item> {
        self.line_buf.clear();
        match self.reader.read_line(&mut self.line_buf) {
            Ok(0) => None, // EOF
            Ok(_) => {
                let trimmed = self.line_buf.trim();
                if trimmed.is_empty() {
                    self.next() // Skip empty lines
                } else {
                    Some(
                        serde_json::from_str(trimmed)
                            .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))
                    )
                }
            }
            Err(e) => Some(Err(e)),
        }
    }
}

/// High-performance buffered NDJSON writer
pub struct NdjsonWriter<W: Write> {
    writer: BufWriter<W>,
}

impl<W: Write> NdjsonWriter<W> {
    pub fn new(writer: W) -> Self {
        Self {
            writer: BufWriter::with_capacity(64 * 1024, writer),
        }
    }

    pub fn to_stdout() -> NdjsonWriter<io::Stdout> {
        NdjsonWriter::new(io::stdout())
    }

    pub fn write(&mut self, record: &Value) -> io::Result<()> {
        serde_json::to_writer(&mut self.writer, record)
            .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
        self.writer.write_all(b"\n")
    }

    pub fn flush(&mut self) -> io::Result<()> {
        self.writer.flush()
    }
}

impl<W: Write> Drop for NdjsonWriter<W> {
    fn drop(&mut self) {
        let _ = self.flush();
    }
}

/// Read all binary data from stdin
pub fn read_binary() -> io::Result<Vec<u8>> {
    let mut buf = Vec::new();
    io::stdin().lock().read_to_end(&mut buf)?;
    Ok(buf)
}

/// Write binary data to stdout
pub fn write_binary(data: &[u8]) -> io::Result<()> {
    let stdout = io::stdout();
    let mut handle = stdout.lock();
    handle.write_all(data)?;
    handle.flush()
}

/// Streaming binary copy (constant memory)
pub fn stream_binary() -> io::Result<u64> {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut stdin = stdin.lock();
    let mut stdout = BufWriter::new(stdout.lock());
    io::copy(&mut stdin, &mut stdout)
}
```

### CLI Module (`jn-plugin/src/cli.rs`)

```rust
use clap::{Parser, ValueEnum};
use std::io;

#[derive(Clone, Copy, Debug, PartialEq, ValueEnum)]
pub enum Mode {
    Read,
    Write,
    Raw,
}

/// Base arguments shared by all plugins
#[derive(Parser, Debug)]
pub struct BaseArgs {
    /// Operation mode
    #[arg(long, value_enum)]
    pub mode: Option<Mode>,

    /// Limit output records
    #[arg(long)]
    pub limit: Option<usize>,

    /// Output plugin metadata as JSON
    #[arg(long)]
    pub jn_meta: bool,
}

/// Plugin metadata for --jn-meta output
#[derive(serde::Serialize)]
pub struct PluginMeta {
    pub name: &'static str,
    pub version: &'static str,
    pub description: &'static str,
    pub modes: Vec<&'static str>,
    pub matches: Vec<&'static str>,
}

impl PluginMeta {
    pub fn print(&self) {
        println!("{}", serde_json::to_string_pretty(self).unwrap());
    }
}

/// Run a plugin with standard error handling
pub fn run<F>(f: F) -> !
where
    F: FnOnce() -> io::Result<()>,
{
    match f() {
        Ok(()) => std::process::exit(0),
        Err(e) if e.kind() == io::ErrorKind::BrokenPipe => {
            std::process::exit(0)
        }
        Err(e) => {
            eprintln!("Error: {}", e);
            std::process::exit(1)
        }
    }
}

/// Macro for defining plugin with minimal boilerplate
#[macro_export]
macro_rules! define_plugin {
    (
        name: $name:literal,
        version: $version:literal,
        description: $desc:literal,
        matches: [$($pattern:literal),* $(,)?],
        modes: [$($mode:ident),* $(,)?],
        args: $args:ty,
        run: $run_fn:expr $(,)?
    ) => {
        fn main() {
            use clap::Parser;
            use $crate::cli::{BaseArgs, Mode, PluginMeta, run};

            #[derive(Parser)]
            #[command(name = $name, version = $version, about = $desc)]
            struct FullArgs {
                #[command(flatten)]
                base: BaseArgs,

                #[command(flatten)]
                custom: $args,
            }

            let args = FullArgs::parse();

            // Handle --jn-meta
            if args.base.jn_meta {
                let meta = PluginMeta {
                    name: $name,
                    version: $version,
                    description: $desc,
                    modes: vec![$(stringify!($mode).to_lowercase()),*],
                    matches: vec![$($pattern),*],
                };
                meta.print();
                return;
            }

            // Require mode
            let mode = match args.base.mode {
                Some(m) => m,
                None => {
                    eprintln!("Error: --mode is required");
                    std::process::exit(1);
                }
            };

            run(|| $run_fn(mode, args.base, args.custom))
        }
    };
}
```

### Example: CSV Plugin (`csv/src/main.rs`)

```rust
use clap::Parser;
use jn_plugin::{define_plugin, Mode, BaseArgs, NdjsonReader, NdjsonWriter, json, Value};
use std::io::{self, BufRead, Write};

#[derive(Parser, Debug, Default)]
struct CsvArgs {
    /// Field delimiter
    #[arg(long, default_value = ",")]
    delimiter: char,

    /// Number of rows to skip
    #[arg(long, default_value = "0")]
    skip_rows: usize,

    /// Omit header row when writing
    #[arg(long)]
    no_header: bool,
}

define_plugin! {
    name: "csv",
    version: env!("CARGO_PKG_VERSION"),
    description: "Parse CSV/TSV files and convert to/from NDJSON",
    matches: [r".*\.csv$", r".*\.tsv$", r".*\.txt$"],
    modes: [read, write],
    args: CsvArgs,
    run: |mode, base, args| {
        match mode {
            Mode::Read => read_csv(&base, &args),
            Mode::Write => write_csv(&base, &args),
            Mode::Raw => Err(io::Error::new(io::ErrorKind::InvalidInput, "raw mode not supported")),
        }
    },
}

fn read_csv(base: &BaseArgs, args: &CsvArgs) -> io::Result<()> {
    let stdin = io::stdin();
    let mut lines = stdin.lock().lines().skip(args.skip_rows);

    // Read header
    let header: Vec<String> = match lines.next() {
        Some(Ok(line)) => line.split(args.delimiter).map(String::from).collect(),
        Some(Err(e)) => return Err(e),
        None => return Ok(()), // Empty file
    };

    let mut writer = NdjsonWriter::to_stdout();
    let mut count = 0;

    for line_result in lines {
        let line = line_result?;
        if line.trim().is_empty() {
            continue;
        }

        let values: Vec<&str> = line.split(args.delimiter).collect();
        let mut record = serde_json::Map::new();

        for (i, key) in header.iter().enumerate() {
            let value = values.get(i).copied().unwrap_or("");
            record.insert(key.clone(), json!(value));
        }

        writer.write(&Value::Object(record))?;

        count += 1;
        if let Some(limit) = base.limit {
            if count >= limit {
                break;
            }
        }
    }

    Ok(())
}

fn write_csv(base: &BaseArgs, args: &CsvArgs) -> io::Result<()> {
    let reader = NdjsonReader::from_stdin();
    let records: Result<Vec<Value>, _> = reader.collect();
    let records = records?;

    if records.is_empty() {
        return Ok(());
    }

    // Collect all keys preserving order
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
    let delim = args.delimiter.to_string();

    // Write header
    if !args.no_header {
        writeln!(out, "{}", keys.join(&delim))?;
    }

    // Write rows
    for record in &records {
        if let Value::Object(map) = record {
            let row: Vec<String> = keys.iter()
                .map(|k| {
                    map.get(k)
                        .and_then(|v| match v {
                            Value::String(s) => Some(s.clone()),
                            Value::Number(n) => Some(n.to_string()),
                            Value::Bool(b) => Some(b.to_string()),
                            Value::Null => Some(String::new()),
                            _ => Some(v.to_string()),
                        })
                        .unwrap_or_default()
                })
                .collect();
            writeln!(out, "{}", row.join(&delim))?;
        }
    }

    Ok(())
}
```

---

## Part 3: Cross-Platform Build & Distribution

### Makefile

```makefile
.PHONY: build release clean install

TARGETS := \
    x86_64-unknown-linux-gnu \
    aarch64-unknown-linux-gnu \
    x86_64-apple-darwin \
    aarch64-apple-darwin \
    x86_64-pc-windows-gnu

PLUGINS := csv json gz ndjson

# Local development build
build:
	cargo build --release

# Cross-compile for all platforms
release:
	@for target in $(TARGETS); do \
		echo "Building for $$target..."; \
		cross build --release --target $$target || exit 1; \
	done
	@$(MAKE) package

# Package binaries with manifests
package:
	@mkdir -p dist
	@for target in $(TARGETS); do \
		os=$$(echo $$target | cut -d- -f3); \
		arch=$$(echo $$target | cut -d- -f1); \
		ext=""; \
		if [ "$$os" = "windows" ]; then ext=".exe"; fi; \
		dir="dist/$$os-$$arch"; \
		mkdir -p $$dir; \
		for plugin in $(PLUGINS); do \
			cp target/$$target/release/$$plugin$$ext $$dir/; \
			cp crates/$$plugin/plugin.json $$dir/$$plugin.json; \
		done; \
	done
	@echo "Packages created in dist/"

# Install to local jn_home
install: build
	@for plugin in $(PLUGINS); do \
		cp target/release/$$plugin ~/.jn/plugins/formats/; \
		cp crates/$$plugin/plugin.json ~/.jn/plugins/formats/$$plugin.json; \
	done
	@echo "Installed to ~/.jn/plugins/formats/"

clean:
	cargo clean
	rm -rf dist
```

### GitHub Actions CI (`release.yml`)

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    strategy:
      matrix:
        include:
          - os: ubuntu-latest
            target: x86_64-unknown-linux-gnu
            artifact: linux-x86_64
          - os: ubuntu-latest
            target: aarch64-unknown-linux-gnu
            artifact: linux-aarch64
            cross: true
          - os: macos-latest
            target: x86_64-apple-darwin
            artifact: darwin-x86_64
          - os: macos-latest
            target: aarch64-apple-darwin
            artifact: darwin-aarch64
          - os: ubuntu-latest
            target: x86_64-pc-windows-gnu
            artifact: windows-x86_64
            cross: true

    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v4

      - name: Install Rust
        uses: dtolnay/rust-action@stable
        with:
          targets: ${{ matrix.target }}

      - name: Install cross
        if: matrix.cross
        run: cargo install cross

      - name: Build
        run: |
          if [ "${{ matrix.cross }}" = "true" ]; then
            cross build --release --target ${{ matrix.target }}
          else
            cargo build --release --target ${{ matrix.target }}
          fi

      - name: Package
        run: |
          mkdir -p artifacts
          for plugin in csv json gz ndjson; do
            ext=""
            if [[ "${{ matrix.target }}" == *"windows"* ]]; then ext=".exe"; fi
            cp target/${{ matrix.target }}/release/${plugin}${ext} artifacts/
            cp crates/${plugin}/plugin.json artifacts/${plugin}.json
          done

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: jn-plugins-${{ matrix.artifact }}
          path: artifacts/

  release:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Download all artifacts
        uses: actions/download-artifact@v4

      - name: Create release archives
        run: |
          for dir in jn-plugins-*; do
            tar -czvf ${dir}.tar.gz -C ${dir} .
          done

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          files: jn-plugins-*.tar.gz
```

---

## Part 4: Distribution Strategies

### Option A: Download on First Use (Recommended)

```python
# In jn's plugin discovery
def ensure_rust_plugins():
    """Download pre-built Rust plugins if not present."""
    plugins_dir = get_plugins_dir() / "bin"
    manifest = plugins_dir / "manifest.json"

    if manifest.exists():
        return  # Already installed

    # Detect platform
    system = platform.system().lower()  # linux, darwin, windows
    machine = platform.machine().lower()  # x86_64, aarch64, arm64

    # Normalize
    if machine in ("arm64", "aarch64"):
        arch = "aarch64"
    else:
        arch = "x86_64"

    platform_key = f"{system}-{arch}"

    # Download from GitHub releases
    url = f"https://github.com/botassembly/jn-plugins-rs/releases/latest/download/jn-plugins-{platform_key}.tar.gz"

    # Download and extract
    download_and_extract(url, plugins_dir)
```

**Pros:**
- Zero build requirements for users
- Fast installation
- Works everywhere

**Cons:**
- Requires GitHub releases infrastructure
- Binary trust issues (mitigated by checksums)

### Option B: Compile on Install

```toml
# pyproject.toml
[tool.setuptools.cmdclass]
build_ext = "build_rust_plugins"

[tool.maturin]
# Use maturin for Rust+Python hybrid builds
```

```python
# setup.py or build hook
class build_rust_plugins(build_ext):
    def run(self):
        # Check for cargo
        if not shutil.which("cargo"):
            print("Warning: Rust not installed, skipping Rust plugins")
            return

        # Clone and build
        subprocess.run(["cargo", "build", "--release"], cwd="jn-plugins-rs")

        # Copy binaries
        for plugin in ["csv", "json", "gz", "ndjson"]:
            shutil.copy(
                f"jn-plugins-rs/target/release/{plugin}",
                f"jn_home/plugins/bin/{plugin}"
            )
```

**Pros:**
- Source-based, auditable
- No binary trust issues

**Cons:**
- Requires Rust toolchain
- Slow installation

### Option C: Optional Package (Hybrid)

```bash
# Basic install (Python plugins only)
pip install jn

# With Rust plugins (downloads pre-built)
pip install jn[fast]

# Build from source
pip install jn[fast-source]
```

**Recommended: Option C** - gives users choice.

---

## Part 5: Discovery Integration

Update `src/jn/plugins/discovery.py`:

```python
def discover_plugins(plugin_dir: Path) -> Dict[str, PluginMetadata]:
    """Discover all plugins (Python and binary)."""
    plugins = {}

    # 1. Discover Python plugins (existing logic)
    for py_file in plugin_dir.rglob("*.py"):
        # ... existing PEP 723 parsing ...

    # 2. Discover binary plugins via sidecar manifests
    for json_file in plugin_dir.rglob("*.json"):
        if json_file.name == "cache.json":
            continue

        try:
            manifest = json.loads(json_file.read_text())
        except json.JSONDecodeError:
            continue

        # Skip if not a plugin manifest
        if "matches" not in manifest:
            continue

        name = manifest.get("name", json_file.stem)

        # Find binary
        binary_path = _find_binary(json_file.parent, name, manifest)
        if not binary_path:
            continue

        plugins[name] = PluginMetadata(
            name=name,
            path=str(binary_path),
            mtime=binary_path.stat().st_mtime,
            matches=manifest.get("matches", []),
            role=manifest.get("role"),
            supports_raw="raw" in manifest.get("modes", []),
            # Binary plugins are self-contained
            dependencies=[],
            requires_python=None,
        )

    return plugins


def _find_binary(directory: Path, name: str, manifest: dict) -> Optional[Path]:
    """Find binary for current platform."""
    # Check platform-specific paths in manifest
    if "binary" in manifest:
        platform_key = _get_platform_key()
        if platform_key in manifest["binary"]:
            binary_name = manifest["binary"][platform_key]
            path = directory / binary_name
            if path.exists() and os.access(path, os.X_OK):
                return path

    # Fallback: look for binary with same name as manifest
    for ext in ["", ".exe"]:
        path = directory / f"{name}{ext}"
        if path.exists() and os.access(path, os.X_OK):
            return path

    return None


def _get_platform_key() -> str:
    """Get platform key like 'linux-x86_64' or 'darwin-aarch64'."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if machine in ("arm64", "aarch64"):
        arch = "aarch64"
    elif machine in ("x86_64", "amd64"):
        arch = "x86_64"
    else:
        arch = machine

    return f"{system}-{arch}"
```

---

## Summary

| Aspect | Solution |
|--------|----------|
| **User plugins** | Sidecar JSON manifest + compiled binary |
| **Bundled plugins** | Cargo workspace with shared `jn-plugin` crate |
| **Cross-platform** | GitHub Actions + `cross` for multi-target builds |
| **Distribution** | Pre-built binaries, downloaded on first use |
| **Discovery** | Unified: PEP 723 for Python, JSON manifest for binaries |
| **Boilerplate** | `define_plugin!` macro handles CLI, errors, metadata |

**User workflow:**
```bash
# Write plugin in Rust
cargo new my_plugin && cd my_plugin
# Add jn-plugin dependency, use define_plugin! macro
cargo build --release
cp target/release/my_plugin ~/.jn/plugins/formats/
echo '{"matches": [".*\\.xyz$"]}' > ~/.jn/plugins/formats/my_plugin.json
jn cat test.xyz  # It works!
```

**Bundled plugin workflow:**
```bash
# In jn-plugins-rs repo
make release      # Cross-compile all platforms
# GitHub Actions uploads to releases
# Users get binaries automatically on `pip install jn[fast]`
```
