# Auto-Generated Manifests: Binary as Source of Truth

**Key Insight:** The manifest is a **cache**, not a source file. The binary's `--jn-meta` output is the source of truth.

---

## Design

### Flow

```
Discovery runs:
  │
  ├─► Find binary (csv_)
  │     │
  │     ├─► Manifest exists (csv_.json)?
  │     │     │
  │     │     ├─► YES: Is binary newer than manifest?
  │     │     │         │
  │     │     │         ├─► NO: Use cached manifest ✓
  │     │     │         │
  │     │     │         └─► YES: Regenerate manifest
  │     │     │
  │     │     └─► NO: Generate manifest
  │     │
  │     └─► Run: ./csv_ --jn-meta
  │           │
  │           └─► Write csv_.json
  │
  └─► Return PluginMetadata
```

### Benefits

1. **Users don't create manifests** - Just drop in a binary
2. **Always in sync** - Manifest regenerated when binary changes
3. **Fast after first run** - Cached like Python plugins
4. **Works for development** - Rebuild binary, manifest auto-updates

---

## Implementation

```python
# src/jn/plugins/discovery.py

import os
import platform
import subprocess
from pathlib import Path

# Binary extensions by platform
BINARY_EXTENSIONS = {
    "windows": [".exe", ".cmd", ".bat"],
    "default": [""],  # Unix: no extension
}


def _get_binary_extensions() -> list[str]:
    """Get valid binary extensions for current platform."""
    system = platform.system().lower()
    if system == "windows":
        return BINARY_EXTENSIONS["windows"]
    return BINARY_EXTENSIONS["default"]


def _is_executable(path: Path) -> bool:
    """Check if path is an executable file."""
    if not path.is_file():
        return False
    # On Unix, check execute permission
    if platform.system() != "Windows":
        return os.access(path, os.X_OK)
    # On Windows, check extension
    return path.suffix.lower() in BINARY_EXTENSIONS["windows"]


def _extract_binary_metadata(binary_path: Path, timeout: float = 5.0) -> dict | None:
    """Extract metadata from binary by running --jn-meta.

    Args:
        binary_path: Path to executable
        timeout: Max seconds to wait

    Returns:
        Parsed JSON metadata or None if extraction fails
    """
    try:
        result = subprocess.run(
            [str(binary_path), "--jn-meta"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            return None

        return json.loads(result.stdout)

    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None


def _load_or_generate_manifest(
    binary_path: Path,
    manifest_path: Path,
) -> dict | None:
    """Load manifest from cache or generate from binary.

    Args:
        binary_path: Path to plugin binary
        manifest_path: Path to JSON manifest (may not exist)

    Returns:
        Manifest dict or None if binary doesn't support --jn-meta
    """
    binary_mtime = binary_path.stat().st_mtime

    # Check if cached manifest is still valid
    if manifest_path.exists():
        try:
            manifest_mtime = manifest_path.stat().st_mtime
            if manifest_mtime >= binary_mtime:
                # Cache is fresh
                manifest = json.loads(manifest_path.read_text())
                if "matches" in manifest:  # Valid plugin manifest
                    return manifest
        except (OSError, json.JSONDecodeError):
            pass  # Regenerate

    # Generate manifest from binary
    metadata = _extract_binary_metadata(binary_path)
    if metadata is None:
        return None

    # Validate it's a plugin manifest
    if "matches" not in metadata and "name" not in metadata:
        return None

    # Add generation metadata
    metadata["_generated"] = True
    metadata["_binary_mtime"] = binary_mtime

    # Write manifest cache
    try:
        manifest_path.write_text(json.dumps(metadata, indent=2))
    except OSError:
        pass  # Continue even if we can't write cache

    return metadata


def discover_binary_plugins(plugin_dir: Path) -> Dict[str, PluginMetadata]:
    """Discover binary plugins, auto-generating manifests as needed."""
    plugins: Dict[str, PluginMetadata] = {}

    if not plugin_dir or not plugin_dir.exists():
        return plugins

    extensions = _get_binary_extensions()

    # Find all potential binary plugins
    for item in plugin_dir.rglob("*"):
        # Skip directories and Python files
        if item.is_dir() or item.suffix == ".py" or item.suffix == ".json":
            continue

        # Skip if not executable
        if not _is_executable(item):
            continue

        # Skip if doesn't look like a plugin (must end with _ or _.<ext>)
        stem = item.stem
        if not stem.endswith("_"):
            continue

        # Determine manifest path
        manifest_path = item.parent / f"{stem}.json"

        # Load or generate manifest
        manifest = _load_or_generate_manifest(item, manifest_path)
        if manifest is None:
            continue

        # Build PluginMetadata
        name = manifest.get("name", stem)
        if not name.endswith("_"):
            name = f"{name}_"

        relative_path = item.relative_to(plugin_dir)

        # Infer role from directory if not in manifest
        role = manifest.get("role")
        if not role:
            rel_str = str(relative_path).replace("\\", "/")
            if "protocols" in rel_str:
                role = "protocol"
            elif "formats" in rel_str:
                role = "format"
            elif "filters" in rel_str:
                role = "filter"
            elif "compression" in rel_str:
                role = "compression"

        plugins[name] = PluginMetadata(
            name=name,
            path=str(item),  # Full path for binaries
            mtime=item.stat().st_mtime,
            matches=manifest.get("matches", []),
            role=role,
            supports_raw=manifest.get("supports_raw", False),
            manages_parameters=manifest.get("manages_parameters", False),
            supports_container=manifest.get("supports_container", False),
            container_mode=manifest.get("container_mode"),
            dependencies=[],  # Not applicable
            requires_python=None,  # Not applicable
        )

    return plugins


def discover_plugins(plugin_dir: Path) -> Dict[str, PluginMetadata]:
    """Discover all plugins: binaries (priority) + Python."""
    plugins: Dict[str, PluginMetadata] = {}

    if not plugin_dir or not plugin_dir.exists():
        return plugins

    # 1. Discover binary plugins first (higher priority)
    binary_plugins = discover_binary_plugins(plugin_dir)
    plugins.update(binary_plugins)

    # 2. Discover Python plugins (don't override binaries)
    for py_file in plugin_dir.rglob("*.py"):
        if py_file.name in ("__init__.py", "__pycache__"):
            continue
        if py_file.name.startswith("test_"):
            continue

        name = py_file.stem
        if name in plugins:
            continue  # Binary takes precedence

        # ... existing PEP 723 parsing ...
        metadata = parse_pep723(py_file)
        tool_jn = metadata.get("tool", {}).get("jn", {})

        # ... rest of existing logic ...

    return plugins
```

---

## Manifest Lifecycle

### First Run (No Manifest)

```bash
$ ls ~/.jn/plugins/formats/
csv_          # Binary only

$ jn cat data.csv
# Discovery runs:
#   1. Finds csv_ binary
#   2. No csv_.json exists
#   3. Runs: ./csv_ --jn-meta
#   4. Writes csv_.json
#   5. Proceeds with csv_ plugin

$ ls ~/.jn/plugins/formats/
csv_          # Binary
csv_.json     # Auto-generated manifest
```

### Binary Updated (Stale Manifest)

```bash
$ cargo build --release  # Rebuild csv_
$ cp target/release/csv_ ~/.jn/plugins/formats/

$ jn cat data.csv
# Discovery runs:
#   1. Finds csv_ binary (mtime: 2024-01-15 10:00)
#   2. csv_.json exists (mtime: 2024-01-14 09:00)
#   3. Binary is newer → regenerate
#   4. Runs: ./csv_ --jn-meta
#   5. Overwrites csv_.json
```

### Cached (Fast Path)

```bash
$ jn cat data.csv
# Discovery runs:
#   1. Finds csv_ binary (mtime: 2024-01-15 10:00)
#   2. csv_.json exists (mtime: 2024-01-15 10:00)
#   3. Manifest is fresh → use cached
#   4. No subprocess spawned ✓
```

---

## --jn-meta Output Format

Standardized across all plugins (Python and Rust):

```json
{
  "name": "csv",
  "version": "0.1.0",
  "description": "Parse CSV/TSV files and convert to/from NDJSON",
  "matches": [
    ".*\\.csv$",
    ".*\\.tsv$"
  ],
  "role": "format",
  "modes": ["read", "write"],
  "supports_raw": false,
  "manages_parameters": false,
  "supports_container": false,
  "container_mode": null
}
```

### Rust Implementation (in jn-plugin crate)

```rust
// Already in define_plugin! macro
if args.base.jn_meta {
    let meta = PluginMeta {
        name: $name,
        version: env!("CARGO_PKG_VERSION"),
        description: $desc,
        matches: vec![$($pattern),*],
        modes: vec![$(stringify!($mode).to_lowercase()),*],
        // ... other fields from macro args
    };
    println!("{}", serde_json::to_string_pretty(&meta).unwrap());
    std::process::exit(0);
}
```

### Python Implementation (in jn_plugin core)

```python
# Already in Plugin._output_metadata()
def _output_metadata(self) -> None:
    meta = {
        "name": self.name,
        "version": getattr(self, "version", "0.0.0"),
        "description": self.description,
        "matches": self._matches,
        "modes": [],
        "supports_raw": getattr(self, "supports_raw", False),
        # ... other fields
    }
    if self._read_fn:
        meta["modes"].append("read")
    # ...
    print(json.dumps(meta, indent=2))
```

---

## Edge Cases

### Binary Without --jn-meta Support

```bash
$ ./old_plugin --jn-meta
Unknown option: --jn-meta
$ echo $?
1
```

**Behavior:** Plugin is skipped (returns None from `_extract_binary_metadata`)

### Manifest Without Binary

```bash
$ ls ~/.jn/plugins/formats/
csv_.json     # Manifest only, no binary
```

**Behavior:** Skipped - discovery looks for executables first

### Permission Issues

```bash
$ ls -la ~/.jn/plugins/formats/
-rw-r--r-- csv_     # Not executable
```

**Behavior:** Skipped by `_is_executable()` check

### Slow Plugin Startup

```python
result = subprocess.run(
    [str(binary_path), "--jn-meta"],
    timeout=5.0,  # 5 second timeout
)
```

**Behavior:** Times out, plugin skipped with warning

---

## Summary

| Scenario | Action |
|----------|--------|
| Binary + no manifest | Generate via `--jn-meta` |
| Binary + stale manifest | Regenerate |
| Binary + fresh manifest | Use cache (fast) |
| Manifest + no binary | Ignored |
| Binary without `--jn-meta` | Skipped |

**User experience:** Just drop in a binary. Manifest appears automatically.
