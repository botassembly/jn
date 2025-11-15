# JN v5 Architecture

**Status:** Implemented (as of Nov 2025)
**See also:**
- `spec/design/addressability.md` - Universal addressing syntax
- `spec/design/profiles.md` - Profile curation system
- `spec/arch/backpressure.md` - Pipeline streaming architecture

---

## Core Architecture

JN v5 uses **plugins as standalone Python scripts** with:
- **PEP 723** for dependencies and metadata
- **UV execution** for isolated environments
- **NDJSON** as universal interchange format
- **Unix pipes** for streaming and backpressure
- **Regex pattern matching** for plugin discovery

---

## Plugin Structure

### Plugin Location
```
jn_home/plugins/
├── formats/         # Bidirectional (reads + writes)
│   ├── csv_.py
│   ├── json_.py
│   ├── yaml_.py
│   └── table_.py
├── filters/         # Transform only
│   └── jq_.py
└── protocols/       # Remote sources (reads, optionally writes)
    ├── http_.py
    ├── gmail_.py
    └── mcp_.py
```

### Plugin Template

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = [".*\\.csv$", ".*\\.tsv$"]
# ///

import sys, csv, json

def reads(config=None):
    """Read from stdin, yield NDJSON."""
    reader = csv.DictReader(sys.stdin)
    for row in reader:
        yield row

def writes(config=None):
    """Read NDJSON from stdin, write to stdout."""
    records = [json.loads(line) for line in sys.stdin]
    writer = csv.DictWriter(sys.stdout, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['read', 'write'], required=True)
    args = parser.parse_args()

    if args.mode == 'read':
        for record in reads():
            print(json.dumps(record))
    else:
        writes()
```

**Key features:**
- UV shebang for direct execution
- PEP 723 TOML metadata
- `reads()` and/or `writes()` functions
- CLI `--mode` argument

---

## Profile Structure

```
jn_home/profiles/
├── http/
│   └── genomoncology/
│       ├── _meta.json          # Connection config
│       ├── alterations.json    # Source endpoint
│       └── trials.json
├── gmail/
│   ├── _meta.json
│   ├── inbox.json
│   └── sent.json
└── mcp/
    └── biomcp/
        ├── _meta.json
        └── search.json
```

**Hierarchical structure:**
- `_meta.json` - Connection config (base_url, auth, timeout)
- `{source}.json` - Endpoint config (path, params, defaults)

**See:** `spec/design/profiles.md` for complete profile system

---

## Discovery & Registry

### Plugin Discovery

1. Scan `jn_home/plugins/` for `*.py` files
2. Parse PEP 723 metadata using regex (no execution)
3. Cache with timestamp-based invalidation
4. Fallback search: custom plugins → user plugins → bundled plugins

**Cache:** `jn_home/cache.json`

### Pattern Matching

Plugins declare regex patterns they handle:
```toml
[tool.jn]
matches = [
  ".*\\.csv$",           # CSV files
  "^https?://.*",        # HTTP URLs
  "@\\w+/.*"             # Profile references
]
```

**Registry:** Compiles all patterns, sorts by specificity (longest match wins)

**See:** `src/jn/plugins/discovery.py`, `src/jn/plugins/registry.py`

---

## Pipeline Execution

### Two-Stage Resolution

For URLs with binary formats:
```
http://example.com/data.xlsx
  ↓
Stage 1: Protocol (http_) - download bytes
  ↓
Stage 2: Format (xlsx_) - parse to NDJSON
  ↓
NDJSON stream
```

For text formats:
```
http://example.com/data.json
  ↓
Single stage: http_ plugin handles download + parsing
  ↓
NDJSON stream
```

**See:** `src/jn/core/pipeline.py`

### Subprocess Pipeline

```bash
jn cat data.csv | jn filter '.revenue > 1000' | jn put output.json
```

Becomes:
```bash
csv_.py --mode read < data.csv | \
jq_.py '.revenue > 1000' | \
json_.py --mode write > output.json
```

**Three processes running concurrently:**
- OS pipes provide automatic backpressure
- SIGPIPE propagates early termination
- Constant memory regardless of data size

**See:** `spec/arch/backpressure.md`

---

## Addressing System

**Five address types:**

1. **Files:** `data.csv`, `/path/to/file.json`
2. **Protocol URLs:** `http://...`, `s3://...`, `gmail://...`
3. **Profile references:** `@genomoncology/alterations?gene=BRAF`
4. **Stdin/stdout:** `-` or `-~csv`
5. **Plugin references:** `@table`, `@json`

**Query strings for parameters:**
```bash
jn cat "@genomoncology/alterations?gene=BRAF&limit=10"
jn cat "@gmail/inbox?from=boss&is=unread"
jn put "-~table.grid"
```

**See:** `spec/design/addressability.md`

---

## Key Design Principles

### 1. Standard Over Custom
- Use PEP 723 (not custom META comments)
- Use NDJSON (not custom binary formats)
- Use Unix pipes (not async/await)

### 2. Streaming by Default
- All data flows through pipes
- Constant memory usage
- Early termination support
- Automatic backpressure

### 3. Plugin Simplicity
- Standalone Python scripts
- 2-4 functions maximum
- UV handles dependencies
- No framework imports required

### 4. Profile Curation
- Profiles curate APIs, not just expose them
- Sources with defaults and adapters
- Targets with validation
- Enum-based differentiation

### 5. Agent-Friendly
- Discoverable (filesystem-based)
- Parseable (JSON + regex metadata)
- Generatable (string templating)
- Composable (multi-source pipelines)

---

## Performance Characteristics

**Memory:** Constant ~1MB regardless of file size

**Latency:**
- Plugin discovery: <10ms (cache hit)
- Pattern matching: <1ms per source
- Pipeline startup: <100ms

**Throughput:**
- Limited by slowest plugin
- OS pipes prevent memory overflow
- Multi-CPU parallelism (3+ concurrent processes)

**Early termination:**
```bash
jn cat large.csv | head -n 10
# Processes only ~10 rows, not entire file
```

---

## What Changed from Earlier Designs

### Implemented Differently

**Plugin location:**
- ~~Design said: `src/jn/plugins/` (packaged)~~
- **Actually:** `jn_home/plugins/` (user-editable)

**Profile syntax:**
- ~~Design said: Both `@api/source` and `@api:source`~~
- **Actually:** Only `@api/source` works (hierarchical slash syntax)

**Parameter passing:**
- ~~Design said: `-p key=value` flags~~
- **Actually:** Query strings `?key=value&key2=value2`

**Duck typing:**
- ~~Design said: Framework detects functions via AST~~
- **Actually:** Plugins declare via CLI `--mode` argument

### Still Accurate

- ✅ PEP 723 metadata
- ✅ UV execution model
- ✅ NDJSON interchange format
- ✅ Regex pattern matching
- ✅ Timestamp-based caching
- ✅ Hierarchical profiles
- ✅ Subprocess pipeline model

---

## Current Status (Nov 2025)

### Implemented ✅
- Core plugin system (discovery, registry, execution)
- Format plugins (CSV, JSON, YAML, TOML, Markdown, Table, XLSX)
- Protocol plugins (HTTP, Gmail, MCP)
- Filter plugin (jq)
- Profile system (HTTP, Gmail, MCP)
- Query string parameters
- Multi-file concatenation
- Stdin/stdout addressing

### In Progress 🚧
- Profile CLI commands (`jn profile list/info/test`)
- OpenAPI generation
- Source/target adapter system
- Parameter validation

### Future 📋
- S3 protocol plugin
- SQL protocol plugin
- OAuth token refresh
- Schema validation

---

## Related Documents

**Design:**
- `spec/design/addressability.md` - Complete addressing syntax
- `spec/design/profiles.md` - Profile curation system
- `spec/design/plugin-specification.md` - Plugin requirements

**Architecture:**
- `spec/arch/backpressure.md` - Why Popen > async

**Examples:**
- `spec/workflows/gmail-examples.md` - Gmail usage patterns
- `spec/workflows/genomoncology-examples.md` - API usage patterns

**Implementation:**
- `src/jn/plugins/discovery.py` - Plugin discovery
- `src/jn/plugins/registry.py` - Pattern matching
- `src/jn/core/pipeline.py` - Pipeline execution
- `src/jn/profiles/` - Profile resolvers (http, gmail, mcp)
