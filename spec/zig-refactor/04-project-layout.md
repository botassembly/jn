# Project Layout

> **Purpose**: Where everything lives and why it's organized that way.

---

## Repository Structure

```
jn/
├── libs/zig/                 # Shared Zig libraries
│   ├── jn-core/              # Streaming I/O, JSON, errors
│   ├── jn-cli/               # Argument parsing, help
│   ├── jn-plugin/            # Plugin interface, metadata
│   ├── jn-address/           # Address parsing
│   ├── jn-profile/           # Profile loading, resolution
│   └── jn-discovery/         # Plugin scanning, caching
│
├── tools/zig/                # Zig CLI tools
│   ├── jn/                   # Orchestrator (thin dispatcher)
│   ├── jn-cat/               # Universal reader
│   ├── jn-put/               # Universal writer
│   ├── jn-filter/            # ZQ wrapper
│   ├── jn-head/              # First N records
│   ├── jn-tail/              # Last N records
│   ├── jn-join/              # Stream joining
│   ├── jn-merge/             # Source merging
│   ├── jn-analyze/           # Statistics
│   ├── jn-inspect/           # Discovery
│   ├── jn-table/             # Pretty print
│   └── jn-profile/           # Profile CLI
│
├── plugins/                  # Plugin executables
│   ├── zig/                  # High-performance Zig plugins
│   │   ├── csv/              # CSV/TSV format
│   │   ├── json/             # JSON format
│   │   ├── jsonl/            # NDJSON passthrough
│   │   ├── gz/               # Gzip compression
│   │   └── http/             # HTTP protocol
│   │
│   └── python/               # Extensible Python plugins
│       ├── xlsx_.py          # Excel format
│       ├── xml_.py           # XML format
│       ├── gmail_.py         # Gmail protocol
│       ├── mcp_.py           # MCP protocol
│       └── duckdb_.py        # DuckDB database
│
├── zq/                       # ZQ filter engine (Zig)
│
├── jn_home/                  # Bundled defaults
│   ├── plugins/              # Default plugins (symlinked)
│   └── profiles/             # Example profiles
│       ├── http/
│       ├── zq/
│       └── gmail/
│
├── src/jn/                   # Python CLI (legacy, being migrated)
│
├── spec/                     # Documentation
│   ├── zig-refactor/         # Architecture docs (this folder)
│   ├── done/                 # Completed feature specs
│   └── todo/                 # Future feature specs
│
├── tests/                    # Test suite
│
├── build.zig                 # Unified Zig build
├── pyproject.toml            # Python project config
├── Makefile                  # Common commands
└── CLAUDE.md                 # AI assistant context
```

---

## Component Locations

### Libraries (`libs/zig/`)

Shared code used by multiple tools and plugins:

| Library | Purpose | Used By |
|---------|---------|---------|
| `jn-core` | Buffered I/O, JSON parsing, errors | All tools and plugins |
| `jn-cli` | Argument parsing, help generation | All tools |
| `jn-plugin` | Plugin metadata, mode dispatch | All plugins |
| `jn-address` | Address parsing, format detection | jn-cat, jn-put |
| `jn-profile` | Profile loading, env substitution | jn-cat, jn-profile |
| `jn-discovery` | Plugin scanning, pattern matching | jn, jn-cat, jn-put |

### Tools (`tools/zig/`)

CLI executables that compose into pipelines:

| Tool | Binary Name | Purpose |
|------|-------------|---------|
| `jn` | `jn` | Orchestrator, subcommand dispatch |
| `jn-cat` | `jn-cat` | Read any source to NDJSON |
| `jn-put` | `jn-put` | Write NDJSON to any format |
| `jn-filter` | `jn-filter` | Transform with ZQ |
| `jn-head` | `jn-head` | First N records |
| `jn-tail` | `jn-tail` | Last N records |
| `jn-join` | `jn-join` | Hash join with source |
| `jn-merge` | `jn-merge` | Concatenate sources |
| `jn-analyze` | `jn-analyze` | Stream statistics |
| `jn-inspect` | `jn-inspect` | Structure discovery |
| `jn-table` | `jn-table` | Pretty print |
| `jn-profile` | `jn-profile` | Profile management |

### Plugins (`plugins/`)

Format, protocol, and compression handlers:

**Zig plugins** (`plugins/zig/`):
- Fast startup, low memory
- Compiled to single binary per plugin
- Used for common, performance-critical formats

**Python plugins** (`plugins/python/`):
- PEP 723 self-contained scripts
- UV handles dependencies
- Used for complex formats and protocols

---

## Plugin Directory Hierarchy

Plugins are discovered from multiple locations with priority ordering:

```
Priority Order (highest to lowest):

1. Project plugins     .jn/plugins/
                       ├── zig/
                       └── python/

2. User plugins        ~/.local/jn/plugins/
                       ├── zig/
                       └── python/

3. Bundled plugins     $JN_HOME/plugins/
                       ├── zig/
                       └── python/
```

### Priority Rules

1. **Project beats user beats bundled**: Local customizations override defaults
2. **Zig beats Python**: At same priority level, Zig plugins preferred
3. **Longer patterns win**: More specific patterns take precedence

### Example Resolution

For `data.csv`:

```
Search order:
1. .jn/plugins/zig/csv         (if exists, use this)
2. .jn/plugins/python/csv_.py  (if exists, use this)
3. ~/.local/jn/plugins/zig/csv
4. ~/.local/jn/plugins/python/csv_.py
5. $JN_HOME/plugins/zig/csv    ← typically matches here
6. $JN_HOME/plugins/python/csv_.py
```

---

## Profile Directory Hierarchy

Profiles follow similar priority ordering:

```
Priority Order:

1. Project profiles    .jn/profiles/
                       ├── http/
                       ├── zq/
                       └── gmail/

2. User profiles       ~/.local/jn/profiles/
                       ├── http/
                       │   └── myapi/
                       │       ├── _meta.json
                       │       └── users.json
                       └── zq/
                           └── filters/
                               └── active_users.zq

3. Bundled profiles    $JN_HOME/profiles/
                       └── http/
                           └── examples/
```

### Profile Structure

```
profiles/http/myapi/
├── _meta.json          # Base config (auth, base_url)
├── users.json          # Endpoint: GET /users
├── projects.json       # Endpoint: GET /projects
└── orders/
    ├── _meta.json      # Sub-namespace base
    └── pending.json    # Endpoint: GET /orders/pending
```

---

## Specification Documents (`spec/`)

Architecture and design documentation:

```
spec/
├── zig-refactor/           # Current architecture docs
│   ├── 01-vision.md
│   ├── 02-architecture.md
│   ├── 03-users-guide.md
│   ├── ...
│   └── docs-plan.md
│
├── done/                   # Completed feature specs
│   ├── addressability.md
│   ├── profile-usage.md
│   ├── arch-backpressure.md
│   └── ...
│
├── todo/                   # Planned feature specs
│   ├── s3-protocol.md
│   ├── sqlite-database.md
│   └── ...
│
└── README.md               # Spec organization guide
```

---

## Build System

### Zig Build (`build.zig`)

Single build file compiles everything:

```bash
# Build all
zig build

# Build specific tool
zig build jn-cat

# Run tests
zig build test

# Cross-compile
zig build -Dtarget=x86_64-linux
```

### Python Setup (`pyproject.toml`)

For legacy CLI and Python plugins:

```bash
# Install in development mode
pip install -e .

# Run tests
make test

# Type checking
make check
```

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `JN_HOME` | Bundled plugins and profiles | `./jn_home` |
| `JN_PLUGINS` | Additional plugin directories | (none) |
| `JN_PROFILES` | Additional profile directories | (none) |
| `JN_CACHE` | Cache directory | `$JN_HOME/cache` |
| `JN_DEBUG` | Enable debug output | `0` |

---

## Where to Add Things

### New Zig Plugin

1. Create directory: `plugins/zig/myformat/`
2. Add `main.zig` with plugin implementation
3. Add to `build.zig` plugin list
4. Plugin auto-discovered on next run

### New Python Plugin

1. Create file: `plugins/python/myformat_.py`
2. Add PEP 723 header with `[tool.jn]` metadata
3. Plugin auto-discovered on next run

### New CLI Tool

1. Create directory: `tools/zig/jn-mytool/`
2. Add `main.zig` with tool implementation
3. Add to `build.zig` tool list
4. Add subcommand routing in `tools/zig/jn/main.zig`

### New Profile Type

1. Create directory: `jn_home/profiles/mytype/`
2. Add `_meta.json` with base configuration
3. Add endpoint JSON files as needed
4. Document in profile type registry

### New Shared Library

1. Create directory: `libs/zig/jn-mylib/`
2. Add source files
3. Add to `build.zig` library list
4. Import in tools/plugins that need it

---

## Cache Files

JN maintains caches for performance:

```
$JN_HOME/cache/
├── plugins.json            # Plugin metadata cache
└── profiles.json           # Profile index cache
```

Caches are invalidated when:
- File modification times change
- Plugin/profile files are added or removed
- Cache format version changes

Clear caches manually:
```bash
rm -rf $JN_HOME/cache/
```

---

## See Also

- [02-architecture.md](02-architecture.md) - How components interact
- [05-plugin-system.md](05-plugin-system.md) - Plugin development
- [07-profiles.md](07-profiles.md) - Profile configuration
