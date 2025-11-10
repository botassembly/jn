# JN v5 Architecture Design

## Overview

JN v5 is a complete redesign focused on **simplicity, performance, and extensibility**. The core insight: plugins are just Python scripts with standard function signatures, discovered via PEP 723 metadata, matched via regex patterns, and cached for performance.

**Design Principles:**
- **Standard over custom**: PEP 723 TOML instead of META comments
- **Duck typing**: Function presence (`reads`, `writes`, `filters`) determines plugin type
- **Fast discovery**: Timestamp-based caching, regex pattern compilation
- **Unified plugins**: One `csv.py` instead of `csv_reader.py` + `csv_writer.py`
- **Profile-based**: Named resources via `@profile/path` syntax
- **UV-native**: Plugins are directly executable scripts with dependencies

---

## Plugin System

### Plugin Types

Plugins are categorized by the functions they expose:

| Type | Functions | Purpose | Example |
|------|-----------|---------|---------|
| **Format** | `reads()`, `writes()` | Parse/generate file formats | `csv.py`, `yaml.py`, `json.py` |
| **Filter** | `filters()` | Transform NDJSON streams | `jq.py` |
| **Protocol** | `reads()` | Fetch from remote sources | `http.py`, `s3.py`, `mcp.py` |
| **Shell** | `reads()` | Wrap shell commands | `ls.py`, `ps.py` |

**Duck typing:** Framework detects type by checking which functions exist (no explicit type declaration needed).

### Plugin Structure

**Location:** All built-in plugins live in `src/jn/plugins/` (packaged with framework)

```
src/jn/plugins/
├── formats/
│   ├── csv.py        # reads() + writes()
│   ├── yaml.py       # reads() + writes()
│   ├── json.py       # reads() + writes()
│   └── xlsx.py       # reads() + writes()
│
├── filters/
│   └── jq.py         # filters()
│
├── protocols/
│   ├── http.py       # reads()
│   ├── s3.py         # reads()
│   ├── mcp.py        # reads() + writes()
│   └── sql.py        # reads() + writes()
│
└── shell/
    ├── ls.py         # reads()
    └── ps.py         # reads()
```

**User plugins:** Same structure in JN_HOME locations (`.jn/plugins/`, `~/.local/jn/plugins/`)

### Plugin Template

```python
#!/usr/bin/env -S uv run --script
"""Parse CSV files and convert to/from NDJSON."""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = [
#   ".*\\.csv$",
#   ".*\\.tsv$"
# ]
# ///

import sys
import csv
import json

def reads(config=None):
    """Read CSV from stdin, yield NDJSON records."""
    config = config or {}
    reader = csv.DictReader(sys.stdin, delimiter=config.get('delimiter', ','))
    for row in reader:
        yield row

def writes(config=None):
    """Read NDJSON from stdin, write CSV to stdout."""
    config = config or {}
    records = [json.loads(line) for line in sys.stdin if line.strip()]
    if not records:
        return

    writer = csv.DictWriter(sys.stdout, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)

def test():
    """Self-test with real data (no mocks)."""
    # Test implementation
    pass

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['read', 'write'], required=True)
    parser.add_argument('--delimiter', default=',')
    args = parser.parse_args()

    if args.mode == 'read':
        for record in reads({'delimiter': args.delimiter}):
            print(json.dumps(record))
    else:
        writes({'delimiter': args.delimiter})
```

**Key elements:**
1. **UV shebang**: `#!/usr/bin/env -S uv run --script` makes plugin directly executable
2. **PEP 723 block**: Dependencies and metadata in TOML format
3. **`[tool.jn]` section**: Plugin-specific metadata (regex patterns)
4. **Function signatures**: `reads(config=None)`, `writes(config=None)`, `filters(config=None)`
5. **CLI interface**: `--mode` flag to select read vs write behavior
6. **Self-test**: `test()` function for validation

---

## Discovery & Caching

### Discovery Process

**Challenge:** Parsing PEP 723 TOML for every plugin on every invocation is slow.

**Solution:** Timestamp-based caching with incremental updates.

### Cache Design

**Cache location:** `{JN_HOME}/cache.json` in each JN_HOME directory

**Cache structure:**
```json
{
  "version": "5.0.0",
  "cache_time": 1699564800.123,
  "plugins": {
    "csv": {
      "path": "/path/to/csv.py",
      "mtime": 1699564700.456,
      "type": "format",
      "functions": ["reads", "writes"],
      "matches": [".*\\.csv$", ".*\\.tsv$"],
      "dependencies": [],
      "requires_python": ">=3.11"
    },
    "yaml": {
      "path": "/path/to/yaml.py",
      "mtime": 1699564750.789,
      "type": "format",
      "functions": ["reads", "writes"],
      "matches": [".*\\.(yaml|yml)$"],
      "dependencies": ["ruamel.yaml>0.18.0"],
      "requires_python": ">=3.12"
    }
  }
}
```

### Cache Invalidation

**Algorithm:**
1. Read `cache.json` from JN_HOME
2. Scan `plugins/` directory for all `.py` files
3. For each file:
   - If file not in cache → parse and add
   - If file `mtime > cache[file].mtime` → parse and update
   - If cache has entry but file deleted → remove from cache
4. Write updated `cache.json`

**Optimization:** Only scan directories if `plugins/` directory mtime is newer than cache mtime.

**Performance target:** <10ms for cache hit, <100ms for full rebuild

### PEP 723 Parser

```python
import re
import tomllib

# Regex from PEP 723
PEP723_PATTERN = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\n(?P<content>(^#(| .*)$\n)+)^# ///$"
)

def parse_pep723(filepath):
    """Extract PEP 723 metadata from Python file."""
    content = open(filepath).read()
    match = PEP723_PATTERN.search(content)

    if not match or match.group('type') != 'script':
        return {}

    # Extract TOML from comments
    lines = match.group('content').splitlines()
    toml_content = '\n'.join(
        line[2:] if line.startswith('# ') else line[1:]
        for line in lines
    )

    return tomllib.loads(toml_content)
```

### Duck Typing Detection

Use AST module to detect which functions exist:

```python
import ast

def detect_plugin_type(filepath):
    """Determine plugin type by function presence."""
    tree = ast.parse(open(filepath).read())
    functions = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}

    has_reads = 'reads' in functions
    has_writes = 'writes' in functions
    has_filters = 'filters' in functions

    if has_reads and has_writes:
        return 'format'
    elif has_filters:
        return 'filter'
    elif has_reads:
        return 'protocol'  # or 'shell' - requires further heuristics
    else:
        return 'unknown'
```

**Note:** Store function list in cache to avoid re-parsing AST.

---

## Pattern Matching & Registry

### Pattern System

Plugins declare **regex patterns** they handle:

```toml
[tool.jn]
matches = [
  ".*\\.csv$",           # File extension
  "^https?://.*",        # HTTP URLs
  "@\\w+/.*"             # Profile references
]
```

### Registry Building

**At startup (or cache load):**
1. Collect all patterns from all plugins
2. Compile regex patterns
3. Build specificity-ordered list

**Pattern specificity:** Sort by:
1. Pattern length (longer = more specific)
2. Character class restrictions (fewer wildcards = more specific)
3. Plugin priority (user > project > built-in)

**Example ordering:**
```
1. ^s3://bucket-name/.*\.csv$     # Most specific
2. ^s3://.*\.csv$
3. ^s3://.*
4. .*\.csv$
5. .*                              # Least specific (catch-all)
```

### Pattern Matching

```python
def resolve_plugin(source, registry):
    """Find best matching plugin for source."""
    matches = []

    for pattern, plugin in registry.patterns:
        if pattern.regex.match(source):
            matches.append((pattern.specificity, pattern, plugin))

    if not matches:
        return None

    # Return highest specificity match
    matches.sort(reverse=True, key=lambda x: x[0])
    return matches[0][2]
```

**Complexity:** O(n) where n = number of patterns (acceptable for <100 plugins)

**Optimization:** Pattern groups by prefix (`http://`, `s3://`, file extensions) for early rejection

---

## Profile System

### Profile Structure

Profiles are configuration files in JN_HOME locations:

```
~/.local/jn/profiles/
├── http/
│   ├── github.json
│   └── stripe.json
│
├── mcp/
│   └── context7.json
│
├── sql/
│   ├── mydb.json
│   └── mydb/
│       └── active-users.sql
│
└── jq/
    ├── revenue.jq
    └── clean-nulls.jq
```

### Profile Syntax

**Path-based (hierarchical resources):**
```bash
@profile/path/to/resource
```

Examples:
- `@github/repos/anthropics/claude-code/issues` → HTTP GET
- `@mydb/public/users` → SQL table
- `@sql/mydb/public/users` → Fully qualified (no ambiguity)

**Tool-based (named resources):**
```bash
@profile:tool_name
```

Examples:
- `@github:create_issue` → MCP tool
- `@mydb:active-users` → Named SQL query
- `@jq:revenue` → Named jq filter

### Profile Resolution

**Shortcut expansion:**
1. Try `@name` as shortcut (search all profiles for unique match)
2. If collision, require namespace: `@plugin/name`
3. If still ambiguous, error with suggestions

**Example:**
```bash
jn cat @active-users.sql   # Search all SQL profiles for "active-users.sql"
# Found in:
#   - profiles/sql/mydb/active-users.sql
#   - profiles/sql/analytics/active-users.sql
# Error: Ambiguous profile reference. Use:
#   - @mydb/active-users.sql
#   - @analytics/active-users.sql
```

### Profile Caching

Profiles cached separately from plugins:

**Cache location:** `{JN_HOME}/profile-cache.json`

**Cache structure:**
```json
{
  "shortcuts": {
    "active-users.sql": ["sql/mydb/active-users.sql", "sql/analytics/active-users.sql"],
    "revenue.jq": ["jq/revenue.jq"]
  },
  "profiles": {
    "http/github": {
      "path": "/home/user/.local/jn/profiles/http/github.json",
      "mtime": 1699564800.123,
      "config": {
        "base_url": "https://api.github.com",
        "headers": {"Authorization": "Bearer ${GITHUB_TOKEN}"}
      }
    }
  }
}
```

**Invalidation:** Same timestamp-based approach as plugin cache.

---

## Pipeline Execution

### Pipeline Stages

Pipelines have 3 stages:

1. **Source** (protocol or format reader)
2. **Filters** (zero or more transforms)
3. **Target** (format writer)

### Execution Model

**Example:** `jn cat data.csv | jn filter '.revenue > 1000' | jn put output.yaml`

**Pipeline resolution:**
1. `data.csv` matches `.*\.csv$` → `csv` plugin, mode=read
2. `.revenue > 1000` → `jq` plugin filter
3. `output.yaml` matches `.*\.yaml$` → `yaml` plugin, mode=write

**Execution:**
```
csv --mode=read < data.csv | jq --query '.revenue > 1000' | yaml --mode=write > output.yaml
```

**Process tree:**
```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│ csv.reads() │ --> │ jq.filters() │ --> │ yaml.writes()│
└─────────────┘     └──────────────┘     └──────────────┘
     stdin              stdin/stdout          stdout
```

**Backpressure:** Automatic via OS pipe buffers (see `spec/arch/backpressure.md`)

### Mode Detection

Framework determines read vs write by pipeline position:

- **First stage** → read mode (`reads()`)
- **Middle stages** → filter mode (`filters()`)
- **Last stage** → write mode (`writes()`)

Plugins receive `--mode=read` or `--mode=write` flag.

---

## Migration from v4

### Breaking Changes

| v4 Concept | v5 Equivalent | Migration |
|------------|---------------|-----------|
| `csv_reader.py` | `csv.py` with `reads()` | Merge reader+writer into one file |
| `csv_writer.py` | `csv.py` with `writes()` | ↑ |
| `run(config)` | `reads(config)` or `writes(config)` | Split by mode |
| `# META: handles=[".csv"]` | `[tool.jn] matches=[".*\\.csv$"]` | Regex pattern |
| `plugins/readers/` | `plugins/formats/` | Folder rename + restructure |
| `plugins/http/s3_get.py` | `plugins/protocols/s3.py` | Folder rename |
| Registry JSON file | Cache JSON (auto-generated) | Delete registry, rebuild cache |

### Migration Checklist

**For plugin authors:**
- [ ] Merge `*_reader.py` + `*_writer.py` into single `*.py`
- [ ] Rename `run()` → `reads()` and/or `writes()`
- [ ] Convert META comments to PEP 723 `[tool.jn]`
- [ ] Add UV shebang for standalone execution
- [ ] Add `--mode` flag to `__main__` argparse
- [ ] Update test() to test both read and write modes
- [ ] Use regex patterns instead of simple extensions

**For framework:**
- [ ] Rewrite discovery.py with caching
- [ ] Rewrite registry.py with pattern matching
- [ ] Rewrite executor.py for multi-function plugins
- [ ] Rewrite pipeline.py for mode detection
- [ ] Build profile system (v5.1.0)

---

## Performance Optimizations

### 1. Plugin Discovery Cache
- **Target:** <10ms for cached lookups
- **Method:** Timestamp-based invalidation
- **Storage:** One `cache.json` per JN_HOME location

### 2. Regex Pattern Compilation
- **Cache compiled patterns** in memory (not just strings)
- **Group by prefix** for early rejection (http://, s3://, file extensions)
- **Pre-sort by specificity** at cache build time

### 3. Lazy Profile Loading
- **Don't load profile configs** until actually needed
- **Cache profile shortcuts** for fast @name resolution
- **Build shortcut map** incrementally (not all at once)

### 4. Minimal AST Parsing
- **Only parse function names** (not full AST)
- **Cache function list** in plugin cache
- **Re-parse only if mtime changed**

### 5. UV Execution
- **UV caches dependencies** automatically
- **First run slow** (downloads deps), subsequent runs fast
- **No virtualenv overhead** (UV handles isolation)

---

## Addressing Ramifications

This design addresses all 34 ramifications identified:

### Plugin Structure (1-10)
✅ **1-2:** Formats merge readers+writers with reads()/writes() duck typing
✅ **3:** PEP 723 `[tool.jn]` for metadata
✅ **4:** UV shebang for standalone execution
✅ **5:** Plugins in `src/jn/plugins/` (packaged)
✅ **6:** Duck typing + optional `[tool.jn]` type declaration
✅ **7:** AST parsing for function detection, cached
✅ **8:** Protocols folder with `reads()` function
✅ **9:** Filters with `filters()` function, jq profiles
✅ **10:** Simple plugin names (csv, yaml, not csv_reader)

### Discovery & Registry (11-18)
✅ **11:** Regex pattern matching with specificity ordering
✅ **12:** Profile shortcuts with collision detection
✅ **13:** Longest/most-specific match algorithm
✅ **14:** PEP 723 TOML parsing (Python 3.11+)
✅ **15:** Duck typing via AST function detection
✅ **16:** Types replace categories (format/filter/protocol)
✅ **17:** Registry built from matches patterns
✅ **18:** Single pattern matching pipeline

### Execution & Pipeline (19-24)
✅ **19:** Multi-function execution with --mode flag
✅ **20:** Pipeline detects read vs write by stage position
✅ **21:** Executor passes --mode=read or --mode=write
✅ **22:** Protocols stream bytes, formats parse to NDJSON
✅ **23:** Config dict consistent across all functions
✅ **24:** Standard error handling (sys.exit + stderr)

### Profile System (25-28)
✅ **25:** Profile discovery with same caching approach
✅ **26:** Namespace collision handled with error + suggestions
✅ **27:** Profile syntax parser (@profile/path, @profile:tool)
✅ **28:** JQ filters in profiles/jq/ directory

### CLI & UX (29-32)
✅ **29:** Keep `jn run`, add `jn cat` / `jn put` shortcuts
✅ **30:** `jn discover --type format` replaces --category
✅ **31:** Clear error messages with pattern matching details
✅ **32:** Documentation rewrite for v5 patterns

### Testing (33-34)
✅ **33:** Plugin test() tests both reads() and writes()
✅ **34:** Integration tests updated for new plugin names

---

## Implementation Phases

### Phase 1: Core Infrastructure (v5.0.0-alpha1)
- [ ] PEP 723 parser
- [ ] Discovery with caching
- [ ] Registry with pattern matching
- [ ] Executor for multi-function plugins
- [ ] Pipeline builder with mode detection

### Phase 2: Core Plugins (v5.0.0-alpha2)
- [ ] CSV format (reads + writes)
- [ ] YAML format (reads + writes)
- [ ] JSON format (reads + writes)
- [ ] JQ filter

### Phase 3: Protocol Plugins (v5.0.0-beta1)
- [ ] HTTP protocol
- [ ] S3 protocol
- [ ] Local filesystem

### Phase 4: Profile System (v5.1.0)
- [ ] Profile discovery and caching
- [ ] Shortcut resolution
- [ ] Named resources (SQL queries, JQ filters)

### Phase 5: Advanced Features (v5.2.0)
- [ ] MCP protocol plugin
- [ ] SQL protocol plugin
- [ ] Shell command wrappers

---

## Open Questions

1. **Filter function signature:** Should it be `filters(config)` or `transform(config)`?
2. **Protocol two-stage execution:** Should `s3.py` output bytes that pipe to `yaml.py`, or should executor auto-chain them?
3. **Python version requirement:** Require 3.11+ for tomllib, or support 3.8+ with tomli backport?
4. **UV requirement:** Make UV optional (fallback to python) or required?
5. **Cache persistence:** Write cache on every discovery, or only on `jn cache rebuild` command?

---

## Success Metrics

**Performance:**
- Discovery <10ms (cache hit)
- Discovery <100ms (cache rebuild)
- Pattern matching <1ms per source

**Developer Experience:**
- Plugin creation: <50 lines for simple format
- Self-contained: Plugin works standalone with UV
- Testable: Built-in test() function

**User Experience:**
- Intuitive: `jn cat data.csv | jn put output.yaml` just works
- Fast: No startup overhead from plugin discovery
- Flexible: Profiles for APIs, databases, custom sources
