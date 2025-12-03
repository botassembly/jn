# JN Zig Refactor: Implementation Plan

> **Goal**: Migrate JN from Python to a pure Zig core with Python plugin extensibility.

---

## Phase Overview

| Phase | Goal | Key Deliverables |
|-------|------|------------------|
| **1** | Foundation Libraries | libjn-core, libjn-cli, libjn-plugin |
| **2** | Plugin Refactor | Migrate existing Zig plugins to use shared libs |
| **3** | Address & Profile System | Universal addressing, hierarchical profiles |
| **4** | Core CLI Tools | jn-cat, jn-put, jn-filter, jn-head, jn-tail |
| **5** | Plugin Discovery | Polyglot discovery (Zig + Python), caching |
| **6** | HTTP Protocol | Zig HTTP plugin with profile support |
| **7** | Analysis Tools | jn-analyze, jn-inspect, jn-table |
| **8** | Join & Merge | jn-join, jn-merge, jn-sh |
| **9** | Orchestrator | jn command dispatcher |
| **10** | Extended Formats | YAML, TOML, Markdown (Zig) |
| **11** | Testing & Migration | Comprehensive tests, Python compatibility |

---

## Phase 1: Foundation Libraries

**Goal**: Create shared Zig libraries that eliminate boilerplate across all tools and plugins.

**Reference Docs**:
- [02-architecture.md](02-architecture.md) - Component responsibilities
- [04-project-layout.md](04-project-layout.md) - Library locations (`libs/zig/`)
- [08-streaming-backpressure.md](08-streaming-backpressure.md) - I/O patterns

### Deliverables

#### libjn-core (`libs/zig/jn-core/`)
Streaming I/O and JSON handling:
- Buffered reader (64KB stdin, line-by-line)
- Buffered writer (8KB stdout, auto-flush)
- JSON parsing with arena allocator (per-line reset)
- NDJSON writer with proper escaping
- Error handling patterns (stderr, exit codes)
- SIGPIPE handling for graceful shutdown

#### libjn-cli (`libs/zig/jn-cli/`)
Argument parsing:
- Base arguments: `--mode`, `--jn-meta`, `--help`, `--version`
- Custom argument registration API
- Type-safe parsing (string, int, bool, enum)
- Help text generation
- Environment variable fallback

#### libjn-plugin (`libs/zig/jn-plugin/`)
Plugin interface:
- PluginMeta struct (name, version, matches, role, modes)
- `--jn-meta` JSON output
- Mode dispatch (read, write, raw, profiles)
- `pluginMain()` entry point pattern

### Build System
- Create `libs/zig/build.zig` for library compilation
- Create root `build.zig` that includes libs + tools + plugins
- Cross-compilation targets (linux, macos, windows)

---

## Phase 2: Plugin Refactor

**Goal**: Refactor existing Zig plugins to use shared libraries, eliminating duplicated code.

**Reference Docs**:
- [05-plugin-system.md](05-plugin-system.md) - Plugin interface
- [04-project-layout.md](04-project-layout.md) - Plugin locations (`plugins/zig/`)

### Deliverables

#### CSV Plugin (`plugins/zig/csv/`)
- Use libjn-core for streaming
- Use libjn-plugin for entry point
- Add delimiter auto-detection (sample first 50 lines)
- Extension hints (.tsv → tab, .csv → comma)

#### JSON Plugin (`plugins/zig/json/`)
- Refactor to use shared libraries
- Add write mode (pretty-print with indent option)
- Array detection and streaming extraction

#### JSONL Plugin (`plugins/zig/jsonl/`)
- Simplest refactor (mostly passthrough)
- Optional validation mode

#### GZ Plugin (`plugins/zig/gz/`)
- Use shared libraries for I/O
- Keep comprezz.zig as local dependency
- Raw mode (bytes in, bytes out)

### Metrics
- Document lines of code reduction per plugin
- Verify tests still pass
- Benchmark before/after

---

## Phase 3: Address & Profile System

**Goal**: Implement universal addressing and hierarchical profile resolution in Zig.

**Reference Docs**:
- [06-matching-resolution.md](06-matching-resolution.md) - Address parsing, pattern matching
- [07-profiles.md](07-profiles.md) - Profile hierarchy, environment substitution

### Deliverables

#### Address Parser (`libs/zig/jn-address/`)
Parse: `[protocol://]path[~format][?params]`
- Protocol detection (http://, duckdb://, etc.)
- Format override extraction (~csv, ~json)
- Query parameter parsing (?key=value)
- Compression detection (.gz, .bz2, .xz)
- Profile reference detection (@namespace/name)
- Glob pattern detection (*, **, ?)

#### Profile System (`libs/zig/jn-profile/`)
- Directory discovery (project → user → bundled)
- JSON loading with hierarchical merge (_meta.json + endpoint.json)
- Environment variable substitution (${VAR}, ${VAR:-default})
- Profile reference parsing (@namespace/name?params)

#### ZQ Profile Support
- Scan `profiles/zq/**/*.zq` files
- Extract description from `#` comments
- Parameter substitution ($param references)

---

## Phase 4: Core CLI Tools

**Goal**: Implement the core CLI tools that form the JN pipeline.

**Reference Docs**:
- [02-architecture.md](02-architecture.md) - Tool responsibilities
- [03-users-guide.md](03-users-guide.md) - Command usage
- [08-streaming-backpressure.md](08-streaming-backpressure.md) - Pipeline construction

### Deliverables

#### jn-cat (`tools/zig/jn-cat/`)
Universal reader:
- Source detection (file, stdin, URL, profile, glob)
- Format inference from extension
- Format override (~format)
- Compression detection and decompression stage
- Multi-stage pipeline construction
- Proper stdout.close() for SIGPIPE

#### jn-put (`tools/zig/jn-put/`)
Universal writer:
- Format inference from extension
- Format override (~format)
- Compression insertion
- Atomic file write (temp + rename)

#### jn-filter (`tools/zig/jn-filter/`)
ZQ wrapper:
- Find ZQ binary (bundled → PATH)
- Parse filter expression
- Resolve profile references
- Direct exec to ZQ (no intermediate process)

#### jn-head / jn-tail (`tools/zig/jn-head/`, `tools/zig/jn-tail/`)
Stream truncation:
- `-n N` argument (default 10)
- head: Count and exit (triggers SIGPIPE)
- tail: Circular buffer, output at EOF

---

## Phase 5: Plugin Discovery

**Goal**: Implement polyglot plugin discovery that finds both Zig and Python plugins.

**Reference Docs**:
- [05-plugin-system.md](05-plugin-system.md) - Discovery process
- [10-python-plugins.md](10-python-plugins.md) - PEP 723 parsing
- [06-matching-resolution.md](06-matching-resolution.md) - Pattern matching

### Deliverables

#### Discovery Service (`libs/zig/jn-discovery/`)

**Zig Plugin Discovery**:
- Scan plugin directories for executables
- Execute with `--jn-meta`, parse JSON response
- Extract: path, matches, modes, role

**Python Plugin Discovery** (no execution):
- Scan for `*.py` files with UV shebang
- Parse PEP 723 `# /// script` block
- Extract `[tool.jn]` metadata via regex
- No Python execution required

#### Pattern Registry
- Compile regex patterns (or optimize to simple matchers)
- Specificity scoring (pattern length)
- Priority ordering (user > bundled, Zig > Python)
- Mode support checking

#### Cache System
- Store metadata in `$JN_HOME/cache/plugins.json`
- Validate with file modification times
- Incremental updates

---

## Phase 6: HTTP Protocol

**Goal**: Implement HTTP protocol plugin in Zig for high-performance API access.

**Reference Docs**:
- [05-plugin-system.md](05-plugin-system.md) - Protocol plugins
- [07-profiles.md](07-profiles.md) - HTTP profile details

### Deliverables

#### HTTP Plugin (`plugins/zig/http/`)
- HTTP/HTTPS client (evaluate: Zig std.http vs libcurl binding)
- TLS support with CA certificates
- Response streaming to stdout (raw mode)
- Header injection from profiles
- Authentication: Bearer, Basic, API key
- Timeout and retry configuration
- Redirect following

#### Profile Integration
- Load HTTP profiles from filesystem
- Query plugin for bundled profiles (--mode=profiles)
- Merge: base_url + path + headers

---

## Phase 7: Analysis Tools

**Goal**: Implement data analysis and discovery tools.

**Reference Docs**:
- [02-architecture.md](02-architecture.md) - Tool purposes
- [03-users-guide.md](03-users-guide.md) - Usage examples

### Deliverables

#### jn-analyze (`tools/zig/jn-analyze/`)
Single-pass statistics:
- Record count
- Field frequency and types
- Numeric stats (min, max, mean, stddev)
- String stats (length distribution)
- Null/missing tracking
- Sample collection

#### jn-inspect (`tools/zig/jn-inspect/`)
Discovery and analysis:
- Profile-based endpoint discovery
- Schema inference from data sample
- Output formatting (JSON, table)

#### jn-table (`tools/zig/jn-table/`)
Pretty print:
- Column width calculation (sample-based)
- Table formats (simple, grid, markdown)
- Terminal width detection
- Wide column truncation

---

## Phase 8: Join & Merge

**Goal**: Implement multi-source data operations.

**Reference Docs**:
- [09-joining-operations.md](09-joining-operations.md) - Join/merge architecture

### Deliverables

#### jn-join (`tools/zig/jn-join/`)
Hash join:
- Right source buffered in hash map
- Left source streams through
- Join modes: natural, named, composite keys
- Join types: left (default), inner
- Output modes: flat merge, embed as array
- Aggregation functions: count, sum, avg, min, max
- Condition joins (--where expression)

#### jn-merge (`tools/zig/jn-merge/`)
Source concatenation:
- Multiple source arguments
- Source tagging (_source, _label fields)
- Custom labels (source:label=Name)
- Error handling: fail-safe vs fail-fast

#### jn-sh (`tools/zig/jn-sh/`)
Shell integration:
- Execute shell commands
- Parse output to NDJSON
- Common parsers (ls, ps, df, env)
- jc integration as fallback

---

## Phase 9: Orchestrator

**Goal**: Implement the main `jn` command that dispatches to tools.

**Reference Docs**:
- [02-architecture.md](02-architecture.md) - Orchestrator role

### Deliverables

#### jn Command (`tools/zig/jn/`)
Thin dispatcher:
- Subcommand routing (cat → jn-cat, put → jn-put, etc.)
- Tool discovery (scan PATH for jn-* binaries)
- Help aggregation from tools
- Version reporting
- Pass-through arguments

#### jn-profile (`tools/zig/jn-profile/`)
Profile CLI:
- `list` - List all profiles (query all plugins)
- `info @ref` - Show profile details
- `discover <url>` - Dynamic discovery

---

## Phase 10: Extended Formats

**Goal**: Add Zig implementations for additional formats.

**Reference Docs**:
- [05-plugin-system.md](05-plugin-system.md) - Format plugins

### Deliverables

#### YAML Plugin (`plugins/zig/yaml/`)
- Evaluate parser options (zig-yaml or custom)
- Read: YAML → NDJSON
- Write: NDJSON → YAML
- Multi-document support

#### TOML Plugin (`plugins/zig/toml/`)
- TOML parser
- Read: TOML → NDJSON
- Write: NDJSON → TOML

#### Markdown Plugin (`plugins/zig/markdown/`)
- Table parsing
- Table generation from NDJSON
- Alignment handling

### Python Fallbacks
These formats remain as Python plugins due to complexity:
- xlsx (openpyxl)
- xml (lxml)
- gmail (Google APIs)
- mcp (Model Context Protocol)
- duckdb (database bindings)
- parquet (PyArrow)

---

## Phase 11: Testing & Migration

**Goal**: Comprehensive testing and smooth migration from Python.

**Reference Docs**:
- All documents for expected behavior

### Deliverables

#### Test Infrastructure
- Unit tests for all libraries
- Integration tests (stdin → tool → stdout)
- End-to-end pipeline tests
- Backpressure verification tests
- Performance benchmarks vs Python

#### Python Compatibility
- Thin Python wrapper that delegates to Zig tools
- Backwards compatibility for existing users
- Deprecation warnings for removed features

#### Documentation
- Update CLAUDE.md with new architecture
- Tool man pages
- Plugin development guide

---

## Success Metrics

| Metric | Python Baseline | Zig Target |
|--------|-----------------|------------|
| Startup time | 50-100ms | <5ms |
| Memory (10MB file) | ~50MB | ~1MB |
| Memory (1GB file) | ~500MB+ | ~1MB |
| Plugin boilerplate | N/A | <50 lines |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Zig HTTP/TLS complexity | Use libcurl binding if std.http insufficient |
| YAML/TOML parser availability | Keep Python plugins as fallback |
| Cross-platform testing | CI matrix with Linux, macOS, Windows |
| User migration friction | Python compatibility layer, gradual rollout |

---

## Quick Reference: Documents by Phase

| Phase | Primary Documents |
|-------|-------------------|
| 1-2 | [02-architecture](02-architecture.md), [04-project-layout](04-project-layout.md), [05-plugin-system](05-plugin-system.md), [08-streaming-backpressure](08-streaming-backpressure.md) |
| 3 | [06-matching-resolution](06-matching-resolution.md), [07-profiles](07-profiles.md) |
| 4 | [02-architecture](02-architecture.md), [03-users-guide](03-users-guide.md), [08-streaming-backpressure](08-streaming-backpressure.md) |
| 5 | [05-plugin-system](05-plugin-system.md), [06-matching-resolution](06-matching-resolution.md), [10-python-plugins](10-python-plugins.md) |
| 6-7 | [05-plugin-system](05-plugin-system.md), [07-profiles](07-profiles.md) |
| 8 | [09-joining-operations](09-joining-operations.md) |
| 9-11 | [02-architecture](02-architecture.md), [03-users-guide](03-users-guide.md) |
