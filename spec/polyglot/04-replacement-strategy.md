# Rust Plugin Architecture: Complete Replacement Strategy

**Goal:** Replace all Python format/compression plugins with Rust. Not optional - these become the default bundled plugins.

---

## 1. Bundling: Rust Replaces Python

### Directory Structure (After Migration)

```
jn_home/
├── plugins/
│   ├── formats/           # Rust binaries (no Python)
│   │   ├── csv_               # Binary
│   │   ├── csv_.json          # Manifest
│   │   ├── json_
│   │   ├── json_.json
│   │   ├── yaml_
│   │   ├── yaml_.json
│   │   └── ...
│   │
│   ├── compression/       # Rust binaries
│   │   ├── gz_
│   │   └── gz_.json
│   │
│   ├── protocols/         # KEEP Python (complex, not hot-path)
│   │   ├── http_.py       # requests library, profile resolution
│   │   ├── gmail_.py      # OAuth, Gmail API
│   │   ├── mcp_.py        # MCP protocol (async)
│   │   └── ...
│   │
│   ├── databases/         # KEEP Python (native bindings are fine)
│   │   └── duckdb_.py     # duckdb-python is already fast
│   │
│   └── filters/           # Thin wrappers (could be Rust or stay Python)
│       └── jq_.py         # Just wraps jq CLI
│
└── bin/                   # Alternative: single bin/ directory
    ├── csv_
    ├── json_
    └── ...
```

### What Gets Replaced vs Stays Python

| Plugin | Current | Replacement | Rationale |
|--------|---------|-------------|-----------|
| csv_.py | Python | **Rust** | Hot path, 10x speedup |
| json_.py | Python | **Rust** | Hot path, simple |
| yaml_.py | Python | **Rust** (serde_yaml) | Moderate benefit |
| toml_.py | Python | **Rust** | Simple |
| xlsx_.py | Python | **Rust** (calamine) | Better streaming |
| xml_.py | Python | **Rust** (quick-xml) | Fast streaming |
| markdown_.py | Python | Python (keep) | Complex parsing, not hot path |
| table_.py | Python | Python (keep) | Output formatting, not hot path |
| gz_.py | Python | **Rust** (flate2) | Streaming, constant memory |
| http_.py | Python | Python (keep) | Profile resolution, requests lib |
| gmail_.py | Python | Python (keep) | OAuth complexity |
| mcp_.py | Python | Python (keep) | Async MCP protocol |
| duckdb_.py | Python | Python (keep) | duckdb-python is optimal |
| jq_.py | Python | Python (keep) | Just wraps jq CLI |

**Summary:** 7 Rust plugins, 7 Python plugins remain.

---

## 2. Comprehensive Manifest Format

### Full Schema (`plugin.json`)

Based on actual `PluginMetadata` fields:

```json
{
  "$schema": "https://jn.dev/schemas/plugin-manifest.json",

  "name": "csv",
  "version": "0.1.0",
  "description": "Parse CSV/TSV files and convert to/from NDJSON",

  "matches": [
    ".*\\.csv$",
    ".*\\.tsv$",
    ".*\\.txt$"
  ],

  "role": "format",

  "modes": ["read", "write"],

  "supports_raw": false,

  "manages_parameters": false,

  "supports_container": false,
  "container_mode": null,

  "binary": {
    "linux-x86_64": "csv_",
    "linux-aarch64": "csv_",
    "darwin-x86_64": "csv_",
    "darwin-aarch64": "csv_",
    "windows-x86_64": "csv_.exe"
  },

  "args": [
    {"name": "delimiter", "type": "string", "default": "auto"},
    {"name": "skip-rows", "type": "int", "default": 0},
    {"name": "no-header", "type": "flag"}
  ]
}
```

### Field Mapping: PEP 723 → JSON Manifest

| PEP 723 Field | JSON Field | Notes |
|---------------|------------|-------|
| `[tool.jn] matches` | `matches` | Regex patterns |
| `[tool.jn] role` | `role` | `format`, `protocol`, `filter`, `compression` |
| `[tool.jn] supports_raw` | `supports_raw` | For raw byte streaming |
| `[tool.jn] manages_parameters` | `manages_parameters` | Plugin handles own params |
| `[tool.jn] supports_container` | `supports_container` | For `jn inspect` |
| `[tool.jn] container_mode` | `container_mode` | How container works |
| `requires-python` | (dropped) | Not needed for binaries |
| `dependencies` | (dropped) | Compiled in |
| - | `binary` | Platform-specific paths |
| - | `args` | CLI argument schema (optional) |

### Protocol Plugin Example (duckdb)

```json
{
  "name": "duckdb",
  "version": "0.1.0",
  "description": "Query DuckDB analytical databases",

  "matches": [
    "^duckdb://.*",
    ".*\\.duckdb$",
    ".*\\.ddb$",
    "^@.*/.*"
  ],

  "role": "protocol",
  "modes": ["read"],

  "manages_parameters": true,
  "supports_container": true,
  "container_mode": "path_count",

  "args": [
    {"name": "query", "type": "string"},
    {"name": "limit", "type": "int"}
  ]
}
```

### How `matches` Works for Non-File Patterns

The registry uses regex matching against the full address:

```python
# File extension: data.csv → matches ".*\.csv$"
# Protocol URL: duckdb://path/db.duckdb → matches "^duckdb://.*"
# Profile ref: @mydb/users → matches "^@.*/.*"
# HTTP URL: https://api.com/data → matches "^https?://.*"
```

**Key insight:** `matches` is NOT just file extensions. It's full regex against the address.

The priority system uses:
1. Explicit format override (`~csv`) → direct lookup
2. Protocol prefix (`duckdb://`) → first match wins
3. File extension → longest pattern match

---

## 3. Build & Bundle Process

### Makefile Target for jn

```makefile
# In main jn repository
RUST_PLUGINS_DIR := jn-plugins-rs
BUNDLE_DIR := jn_home/plugins

.PHONY: build-rust-plugins bundle

# Build Rust plugins for current platform (development)
build-rust-plugins:
	cd $(RUST_PLUGINS_DIR) && cargo build --release

# Bundle into jn_home (for distribution)
bundle: build-rust-plugins
	# Copy binaries
	cp $(RUST_PLUGINS_DIR)/target/release/csv_ $(BUNDLE_DIR)/formats/
	cp $(RUST_PLUGINS_DIR)/target/release/json_ $(BUNDLE_DIR)/formats/
	cp $(RUST_PLUGINS_DIR)/target/release/gz_ $(BUNDLE_DIR)/compression/
	# Copy manifests
	cp $(RUST_PLUGINS_DIR)/crates/csv/plugin.json $(BUNDLE_DIR)/formats/csv_.json
	cp $(RUST_PLUGINS_DIR)/crates/json/plugin.json $(BUNDLE_DIR)/formats/json_.json
	cp $(RUST_PLUGINS_DIR)/crates/gz/plugin.json $(BUNDLE_DIR)/compression/gz_.json
	# Remove replaced Python files
	rm -f $(BUNDLE_DIR)/formats/csv_.py
	rm -f $(BUNDLE_DIR)/formats/json_.py
	rm -f $(BUNDLE_DIR)/compression/gz_.py
```

### Cross-Platform Release Process

```yaml
# .github/workflows/release.yml
jobs:
  build-rust-plugins:
    strategy:
      matrix:
        include:
          - os: ubuntu-latest
            target: x86_64-unknown-linux-gnu
          - os: ubuntu-latest
            target: aarch64-unknown-linux-gnu
            use_cross: true
          - os: macos-latest
            target: x86_64-apple-darwin
          - os: macos-latest
            target: aarch64-apple-darwin
          - os: windows-latest
            target: x86_64-pc-windows-msvc

    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true  # jn-plugins-rs as submodule

      - name: Build Rust plugins
        run: |
          if [ "${{ matrix.use_cross }}" = "true" ]; then
            cargo install cross
            cross build --release --target ${{ matrix.target }}
          else
            cargo build --release --target ${{ matrix.target }}
          fi
        working-directory: jn-plugins-rs

      - name: Package with platform suffix
        run: |
          mkdir -p dist/${{ matrix.target }}/plugins/formats
          mkdir -p dist/${{ matrix.target }}/plugins/compression
          # Copy binaries with manifests
          ...

  package:
    needs: build-rust-plugins
    steps:
      - name: Create platform packages
        # Creates: jn-0.1.0-linux-x86_64.tar.gz, etc.
```

### pip install Integration

```python
# setup.py or pyproject.toml hook
import platform
import urllib.request
import tarfile

def download_rust_plugins():
    """Download pre-built Rust plugins for current platform."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Normalize architecture
    if machine in ('arm64', 'aarch64'):
        arch = 'aarch64'
    else:
        arch = 'x86_64'

    platform_key = f"{system}-{arch}"
    version = get_version()

    url = f"https://github.com/botassembly/jn/releases/download/v{version}/jn-plugins-{platform_key}.tar.gz"

    # Download and extract to jn_home/plugins/
    ...
```

---

## 4. What Python Can Be Replaced with jq Wrappers?

### Current State Analysis

**`filtering.py`** - Framework code that builds jq expressions:
```python
# Converts: ?city=NYC&revenue>1000
# To: select((.city | tostring) == "NYC" and (.revenue | tonumber) > 1000)
```

This is **not a plugin** - it's framework code used by `jn cat` for inline filtering.

**`jq_.py`** - Already a thin wrapper:
```python
# Just builds: jq -c <expression>
# And runs it with subprocess.Popen
```

### Can `filtering.py` Be Replaced?

**Option A: Keep as Python framework code** (Recommended)
- It's not in the hot path (runs once per query, not per record)
- jq does the actual filtering
- Complex logic (operator parsing, OR/AND grouping)

**Option B: Compile to jq expression in Rust**
- Marginal benefit (microseconds saved)
- Adds complexity

**Recommendation:** Keep `filtering.py` as Python. The actual filtering uses jq.

### What About More jq Power?

The current jq_.py plugin could be enhanced:

```python
# Current: just wraps jq
jq -c '.field > 10'

# Could add: jq profiles for common transforms
@transforms/flatten   # .[] | flatten
@transforms/group_by  # group_by(.field) | map({key: .[0].field, values: .})
```

These are already supported via profile resolution - no code change needed.

---

## 5. Updated Plugin Discovery

```python
# src/jn/plugins/discovery.py

def discover_plugins(plugin_dir: Path) -> Dict[str, PluginMetadata]:
    """Discover all plugins (Python and binary)."""
    plugins = {}

    # 1. Discover binary plugins via JSON manifests (higher priority)
    for json_file in plugin_dir.rglob("*.json"):
        if json_file.name in ("cache.json", "manifest.json"):
            continue

        manifest = _load_manifest(json_file)
        if manifest is None:
            continue

        binary_path = _find_binary(json_file.parent, manifest)
        if binary_path is None:
            continue

        name = manifest.get("name", json_file.stem.rstrip("_"))
        plugins[f"{name}_"] = PluginMetadata(
            name=f"{name}_",
            path=str(binary_path),
            mtime=binary_path.stat().st_mtime,
            matches=manifest.get("matches", []),
            role=manifest.get("role"),
            supports_raw=manifest.get("supports_raw", False),
            manages_parameters=manifest.get("manages_parameters", False),
            supports_container=manifest.get("supports_container", False),
            container_mode=manifest.get("container_mode"),
            dependencies=[],  # Not applicable for binaries
            requires_python=None,
        )

    # 2. Discover Python plugins via PEP 723 (fallback)
    for py_file in plugin_dir.rglob("*.py"):
        name = py_file.stem
        if f"{name}" in plugins:
            continue  # Binary takes precedence

        # ... existing PEP 723 parsing ...

    return plugins


def _load_manifest(json_path: Path) -> Optional[dict]:
    """Load and validate plugin manifest."""
    try:
        data = json.loads(json_path.read_text())
        # Must have 'matches' to be a plugin manifest
        if "matches" not in data:
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def _find_binary(directory: Path, manifest: dict) -> Optional[Path]:
    """Find binary for current platform."""
    name = manifest.get("name", "")

    # Check platform-specific binary paths
    if "binary" in manifest:
        platform_key = _get_platform_key()
        if platform_key in manifest["binary"]:
            binary_name = manifest["binary"][platform_key]
            path = directory / binary_name
            if path.exists() and _is_executable(path):
                return path

    # Fallback: look for name_ or name_.exe
    for suffix in ("", ".exe"):
        path = directory / f"{name}_{suffix}"
        if path.exists() and _is_executable(path):
            return path

    return None
```

---

## 6. Invocation: Binary vs Python

The existing invocation code already handles both:

```python
def _build_command(stage: ExecutionStage) -> list[str]:
    """Build command for plugin execution."""

    # Check if it's a binary (no .py extension)
    if stage.plugin_path.endswith(".py"):
        # Python plugin: use uv
        cmd = ["uv", "run", "--quiet", "--script", stage.plugin_path]
    else:
        # Binary plugin: direct execution
        cmd = [stage.plugin_path]

    cmd.extend(["--mode", stage.mode])
    # ... add other args ...

    return cmd
```

**Key change:** Binaries run directly, no `uv run` wrapper.

---

## Summary

| Question | Answer |
|----------|--------|
| **Where do Rust plugins go?** | Same location as Python: `jn_home/plugins/{formats,compression}/` |
| **How bundled?** | Pre-built binaries included in releases, downloaded on install |
| **Replace Python?** | Yes, 7 format/compression plugins → Rust. Not optional. |
| **Manifest complete?** | Yes - covers all current `PluginMetadata` fields |
| **Protocol patterns?** | `matches` is full regex, works with `^duckdb://`, `^@.*/.*`, etc. |
| **jq replacement?** | Keep `filtering.py` (framework code). `jq_.py` already wraps jq. |

### Next Steps

1. Create `jn-plugins-rs/` with workspace structure
2. Implement `jn-plugin` core crate
3. Port csv_, json_, gz_ to Rust
4. Update discovery to prefer binary manifests
5. Add CI for cross-platform builds
6. Remove Python versions of ported plugins
