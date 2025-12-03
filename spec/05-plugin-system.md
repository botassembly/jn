# Plugin System

> **Purpose**: How plugins work and what they can do.

---

## What Is a Plugin?

A plugin is a standalone executable that:
- Reads from stdin
- Writes to stdout
- Accepts a `--mode` argument
- Outputs metadata via `--jn-meta`
- Declares patterns it can handle

Plugins don't import a framework. They're independent programs that follow a simple CLI convention.

---

## Plugin Roles

### Format Plugins

Convert between a specific format and NDJSON.

| Plugin | Patterns | Read | Write |
|--------|----------|------|-------|
| csv | `.*\.csv$`, `.*\.tsv$` | CSV → NDJSON | NDJSON → CSV |
| json | `.*\.json$` | JSON array → NDJSON | NDJSON → JSON array |
| jsonl | `.*\.jsonl$`, `.*\.ndjson$` | Passthrough | Passthrough |
| yaml | `.*\.ya?ml$` | YAML → NDJSON | NDJSON → YAML |
| toml | `.*\.toml$` | TOML → NDJSON | NDJSON → TOML |
| xlsx | `.*\.xlsx$` | Excel → NDJSON | NDJSON → Excel |
| xml | `.*\.xml$` | XML → NDJSON | NDJSON → XML |
| table | (output only) | - | NDJSON → ASCII table |
| markdown | `.*\.md$` (tables) | MD table → NDJSON | NDJSON → MD table |

### Protocol Plugins

Fetch data from remote sources.

| Plugin | Patterns | Purpose |
|--------|----------|---------|
| http | `^https?://` | Fetch from HTTP/HTTPS URLs |
| gmail | `^gmail://` | Read Gmail messages |
| mcp | `^mcp://` | Model Context Protocol |
| duckdb | `^duckdb://`, `.*\.duckdb$` | Query DuckDB databases |

Protocol plugins output raw bytes (mode=raw) or NDJSON directly.

### Compression Plugins

Handle byte-level compression/decompression.

| Plugin | Patterns | Purpose |
|--------|----------|---------|
| gz | `.*\.gz$` | Gzip compression |
| bz2 | `.*\.bz2$` | Bzip2 compression |
| xz | `.*\.xz$` | XZ/LZMA compression |

Compression plugins use `--mode=raw` (bytes in, bytes out).

---

## Plugin Modes

Every plugin supports one or more modes:

### `read` Mode

Convert source format to NDJSON:

```
stdin (source bytes) → plugin --mode=read → stdout (NDJSON)
```

Example: CSV plugin reads CSV, outputs NDJSON records.

### `write` Mode

Convert NDJSON to destination format:

```
stdin (NDJSON) → plugin --mode=write → stdout (destination bytes)
```

Example: CSV plugin reads NDJSON, outputs CSV.

### `raw` Mode

Byte-level passthrough (no JSON):

```
stdin (bytes) → plugin --mode=raw → stdout (bytes)
```

Used by:
- Compression plugins (gz, bz2)
- Protocol plugins fetching binary data
- Format plugins that need raw access

### `profiles` Mode

List and describe available profiles:

```
plugin --mode=profiles --list              # List profiles (NDJSON)
plugin --mode=profiles --info=@name        # Profile details (JSON)
plugin --mode=profiles --discover=<url>    # Dynamic discovery
```

Used by plugins that manage their own profile-like configurations.

---

## Plugin Metadata

Plugins declare their capabilities via metadata.

### Zig Plugins (`--jn-meta`)

```bash
./csv --jn-meta
```

Output:
```json
{
  "name": "csv",
  "version": "0.1.0",
  "matches": [".*\\.csv$", ".*\\.tsv$"],
  "role": "format",
  "modes": ["read", "write"]
}
```

### Python Plugins (PEP 723)

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl"]
# [tool.jn]
# matches = [".*\\.xlsx$"]
# role = "format"
# modes = ["read", "write"]
# ///
```

JN parses the PEP 723 block without executing Python.

### Metadata Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Plugin identifier |
| `version` | No | Semantic version |
| `matches` | Yes | Regex patterns for source matching |
| `role` | No | format, protocol, compression, database |
| `modes` | No | Supported modes (default: all) |
| `profile_type` | No | Profile namespace if profiles mode supported |

---

## Plugin Discovery

### Discovery Process

1. **Scan directories**: Check plugin paths in priority order
2. **Identify plugins**:
   - Zig: Executable files
   - Python: `*.py` files with PEP 723 `[tool.jn]` block
3. **Extract metadata**:
   - Zig: Execute with `--jn-meta`
   - Python: Parse PEP 723 block (no execution)
4. **Build registry**: Map patterns to plugins

### Cache

Discovery results are cached in `$JN_HOME/cache/plugins.json`:
- Includes file modification times
- Invalidated when files change
- Refreshed on next command

### Priority Order

```
1. Project plugins     .jn/plugins/{zig,python}/
2. User plugins        ~/.local/jn/plugins/{zig,python}/
3. Bundled plugins     $JN_HOME/plugins/{zig,python}/
```

Within same priority:
- Zig plugins preferred over Python
- Longer regex patterns preferred (more specific)

---

## Plugin Interface

### Command Line

All plugins accept:

```
plugin --mode={read|write|raw|profiles} [options] [address]
```

Common options:
- `--mode`: Required, determines operation
- `--jn-meta`: Output metadata JSON and exit
- `--help`: Show usage
- `--version`: Show version

Format-specific options:
- `--delimiter=X`: Field separator (CSV)
- `--indent=N`: Indentation level (JSON, YAML)
- `--header={true|false}`: Header row (CSV)

### Input/Output

- **Read mode**: stdin = source bytes, stdout = NDJSON
- **Write mode**: stdin = NDJSON, stdout = destination bytes
- **Raw mode**: stdin = bytes, stdout = bytes

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Usage error |
| 141 | SIGPIPE (normal for pipelines) |

### Error Handling

Errors go to stderr:
```
Error: CSV parsing failed at line 42: unterminated quote
```

Plugins should:
- Report errors clearly with context
- Exit non-zero on failure
- Handle SIGPIPE gracefully

---

## Plugin Communication

### With Orchestrator

The orchestrator (`jn` or `jn-cat`) spawns plugins as subprocesses:

```
jn-cat data.csv
    │
    └── spawns: csv --mode=read
                    stdin ← file contents
                    stdout → pipe to next stage or terminal
```

### Between Plugins

In multi-stage pipelines, plugins communicate via OS pipes:

```
http --mode=raw | gz --mode=raw | csv --mode=read
     │                │                │
     └── bytes ───────┴── bytes ───────┴── NDJSON
```

The OS manages:
- Buffering (64KB pipe buffers)
- Backpressure (blocking writes)
- Shutdown (SIGPIPE propagation)

---

## Writing a Plugin

### Zig Plugin Structure

```
plugins/zig/myformat/
├── main.zig          # Entry point
├── parser.zig        # Format-specific parsing
└── build.zig         # Build configuration
```

The plugin uses shared libraries:
- `libjn-core` for I/O and JSON
- `libjn-cli` for argument parsing
- `libjn-plugin` for metadata and mode dispatch

### Python Plugin Structure

Single file with PEP 723 header:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["some-library"]
# [tool.jn]
# matches = [".*\\.myformat$"]
# role = "format"
# modes = ["read"]
# ///

import sys
import json

def reads(config=None):
    """Read source format, yield records."""
    for line in sys.stdin:
        # Parse line
        yield {"field": "value"}

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['read', 'write'])
    parser.add_argument('--jn-meta', action='store_true')
    args = parser.parse_args()

    if args.jn_meta:
        print(json.dumps({
            "name": "myformat",
            "matches": [".*\\.myformat$"],
            "role": "format",
            "modes": ["read"]
        }))
    elif args.mode == 'read':
        for record in reads():
            print(json.dumps(record))
```

---

## Design Decisions

### Why Standalone Executables?

**Benefits**:
- No framework coupling
- Any language works
- Easy testing (`./plugin --mode=read < test.csv`)
- Clear process boundaries
- OS handles resource isolation

**Trade-offs**:
- Process startup overhead (mitigated by Zig for hot paths)
- No shared state between plugins (by design)

### Why Regex Patterns?

**Benefits**:
- Flexible matching (extensions, protocols, paths)
- Specificity via pattern length
- No registration step

**Trade-offs**:
- Regex parsing complexity
- Potential pattern conflicts (resolved by priority)

### Why Separate Read/Write Modes?

**Benefits**:
- Clear responsibilities
- Can implement one without the other
- Simpler testing

**Trade-offs**:
- Some duplication (e.g., schema knowledge)
- Mode dispatch boilerplate

---

## See Also

- [06-matching-resolution.md](06-matching-resolution.md) - How patterns resolve to plugins
- [10-python-plugins.md](10-python-plugins.md) - Python plugin details
- [04-project-layout.md](04-project-layout.md) - Where plugins live
