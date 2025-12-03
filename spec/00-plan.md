# JN Zig Refactor: Implementation Plan

> **Goal**: Migrate JN from Python to a pure Zig core with Python plugin extensibility.

---

## Phase Overview

| Phase | Goal | Key Deliverables | Dependencies |
|-------|------|------------------|--------------|
| **0** | Quality Foundation | Testing strategy, code quality, demo verification | None |
| **1** | Foundation Libraries | libjn-core, libjn-cli, libjn-plugin | Phase 0 |
| **2** | Plugin Refactor | Migrate existing Zig plugins to use shared libs | Phase 1 |
| **3** | OpenDAL Protocol | Unified protocol plugin (HTTP, S3, HDFS, etc.) | Phase 2 |
| **4** | Address & Profile System | Universal addressing, hierarchical profiles | Phase 1 |
| **5** | Core CLI Tools | jn-cat, jn-put, jn-filter, jn-head, jn-tail | Phases 2, 3, 4 |
| **6** | Plugin Discovery | Polyglot discovery (Zig + Python), caching | Phase 2 |
| **7** | Analysis Tools | jn-analyze, jn-inspect | Phase 5 |
| **8** | Join & Merge | jn-join, jn-merge, jn-sh | Phase 5 |
| **9** | Orchestrator | jn command dispatcher | Phases 5-8 |
| **10** | Extended Formats | YAML, TOML, Markdown (Zig) | Phase 2 |
| **11** | Testing & Migration | Comprehensive tests, Python compatibility | All |

---

## Dependency Graph

```
Phase 0 (Quality Foundation)
    │
    ▼
Phase 1 (Foundation Libraries)
    │
    ├───────────────────┬────────────────────┐
    ▼                   ▼                    ▼
Phase 2              Phase 4             Phase 10
(Plugin Refactor)    (Address/Profile)   (Extended Formats)
    │                   │
    ▼                   │
Phase 3                 │
(OpenDAL Protocol)      │
    │                   │
    └───────┬───────────┘
            ▼
        Phase 5
        (Core CLI Tools)
            │
            ├──────────────────┐
            ▼                  ▼
        Phase 6            Phases 7, 8
        (Discovery)        (Analysis, Join/Merge)
            │                  │
            └───────┬──────────┘
                    ▼
                Phase 9
                (Orchestrator)
                    │
                    ▼
                Phase 11
                (Testing & Migration)
```

---

## Phase 0: Quality Foundation

**Goal**: Establish testing and quality infrastructure before writing code.

**Status**: ✅ COMPLETE (416 tests pass, all quality checks pass)

**Reference Docs**:
- [11-demo-migration.md](11-demo-migration.md) - Demo inventory and migration plan
- [12-testing-strategy.md](12-testing-strategy.md) - Outside-in testing approach
- [13-code-quality.md](13-code-quality.md) - Coverage, linting, formatting

### Deliverables

- [x] Verify all existing tests pass (`make test`)
- [x] Verify code quality checks pass (`make check`)
- [x] Baseline coverage documented
- [x] Demo inventory reviewed

### Exit Criteria ✅
- All tests pass (416 passing)
- All quality checks pass (format, lint, types)
- Python plugin inventory documented

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

#### libjn-plugin (`libs/zig/jn-plugin/`)
Plugin interface:
- PluginMeta struct (name, version, matches, role, modes)
- `--jn-meta` JSON output
- Mode dispatch (read, write, raw, profiles)
- `pluginMain()` entry point pattern

### Build System
- Create `libs/zig/build.zig` for library compilation
- Update root `Makefile` for unified build
- Target: ReleaseFast with `-fllvm`

### Exit Criteria
- [ ] Libraries compile and pass unit tests
- [ ] Example plugin using all three libraries
- [ ] Documentation for library APIs

---

## Phase 2: Plugin Refactor

**Goal**: Refactor existing Zig plugins to use shared libraries, validating the Phase 1 design.

**Reference Docs**:
- [05-plugin-system.md](05-plugin-system.md) - Plugin interface
- [04-project-layout.md](04-project-layout.md) - Plugin locations

### Deliverables

#### CSV Plugin (`plugins/zig/csv/`)
- Use libjn-core for streaming I/O
- Use libjn-cli for argument parsing
- Use libjn-plugin for entry point and manifest

#### JSON Plugin (`plugins/zig/json/`)
- Refactor to use shared libraries
- Add write mode (pretty-print with indent option)

#### JSONL Plugin (`plugins/zig/jsonl/`)
- Simplest refactor (mostly passthrough)
- Validates minimal plugin structure

#### GZ Plugin (`plugins/zig/gz/`)
- Use shared libraries for I/O
- Keep comprezz.zig as local dependency

### Metrics
- Document lines of code reduction per plugin
- Verify all plugin tests still pass
- Benchmark before/after (startup time, throughput)

### Exit Criteria
- [ ] All existing Zig plugins refactored
- [ ] Tests pass for all plugins
- [ ] Code reduction documented (expect >50% less boilerplate)

---

## Phase 3: OpenDAL Protocol Plugin

**Goal**: Implement unified protocol handler for all remote sources using Apache OpenDAL.

**Status**: Prototype verified ✅ (See [opendal-analysis.md](opendal-analysis.md))

**What OpenDAL replaces**:
- ❌ HTTP plugin (originally planned for old Phase 6)
- ❌ Future S3 plugin
- ❌ Future HDFS plugin
- ❌ Future GCS/Azure/FTP plugins

**What OpenDAL provides**:
- 70+ storage backends via single plugin
- Streaming reads (verified with prototype)
- Consistent API across all protocols

### Deliverables

#### Build Integration
- Add OpenDAL C library build to `make install`
- Store in `vendor/opendal/` (already cloned)
- Build with services: fs, http, s3, memory

#### OpenDAL Plugin (`plugins/zig/opendal/`)
Productionize the prototype:
- Scheme routing (s3://, http://, gs://, etc.)
- Streaming output to stdout
- Error handling with meaningful messages
- Use libjn-plugin for manifest

#### Profile Integration
- Load credentials from JN profile system
- Map profile fields to OpenDAL operator options
- Environment variable substitution

### Supported Schemes (Initial)
| Scheme | OpenDAL Service |
|--------|-----------------|
| `http://`, `https://` | http |
| `s3://` | s3 |
| `gs://`, `gcs://` | gcs |
| `az://`, `azblob://` | azblob |
| `hdfs://` | hdfs |
| `ftp://` | ftp |
| `sftp://` | sftp |
| `file://` | fs |

### Exit Criteria
- [ ] OpenDAL plugin reads from HTTP URLs
- [ ] OpenDAL plugin reads from S3 (with credentials)
- [ ] Streaming verified (constant memory on large files)
- [ ] Plugin manifest includes all supported schemes

---

## Phase 4: Address & Profile System

**Goal**: Implement universal addressing and hierarchical profile resolution.

**Reference Docs**:
- [06-matching-resolution.md](06-matching-resolution.md) - Address parsing
- [07-profiles.md](07-profiles.md) - Profile hierarchy

### Deliverables

#### Address Parser (`libs/zig/jn-address/`)
Parse: `[protocol://]path[~format][?params]`
- Protocol detection (s3://, http://, duckdb://, etc.)
- Format override extraction (~csv, ~json)
- Query parameter parsing (?key=value)
- Compression detection (.gz, .bz2, .xz)
- Profile reference detection (@namespace/name)

#### Profile System (`libs/zig/jn-profile/`)
- Directory discovery (project → user → bundled)
- JSON loading with hierarchical merge
- Environment variable substitution (${VAR}, ${VAR:-default})
- Profile reference parsing (@namespace/name?params)

### Exit Criteria
- [ ] Address parser handles all documented formats
- [ ] Profile loader resolves hierarchically
- [ ] Environment substitution works
- [ ] Unit tests for edge cases

---

## Phase 5: Core CLI Tools

**Goal**: Implement the core CLI tools that form the JN pipeline.

**Reference Docs**:
- [02-architecture.md](02-architecture.md) - Tool responsibilities
- [03-users-guide.md](03-users-guide.md) - Command usage
- [08-streaming-backpressure.md](08-streaming-backpressure.md) - Pipeline construction

### Deliverables

#### jn-cat (`tools/zig/jn-cat/`)
Universal reader:
- Parse source with address library
- Route to OpenDAL for remote sources (s3://, http://)
- Route to local plugins for files
- Format inference from extension
- Format override (~format)
- Compression stage insertion
- Proper SIGPIPE handling

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
- Direct exec to ZQ

#### jn-head / jn-tail
Stream truncation:
- `-n N` argument (default 10)
- Efficient early termination

### Exit Criteria
- [ ] `jn-cat file.csv` works (local file)
- [ ] `jn-cat https://...` works (via OpenDAL)
- [ ] `jn-cat s3://...` works (via OpenDAL with creds)
- [ ] `jn-cat data.csv.gz` works (decompression chain)
- [ ] Pipelines work: `jn-cat x | jn-filter '.y' | jn-put z`

---

## Phase 6: Plugin Discovery

**Goal**: Implement polyglot plugin discovery for Zig and Python plugins.

**Reference Docs**:
- [05-plugin-system.md](05-plugin-system.md) - Discovery process
- [10-python-plugins.md](10-python-plugins.md) - PEP 723 parsing

### Deliverables

#### Discovery Service (`libs/zig/jn-discovery/`)

**Zig Plugin Discovery**:
- Scan plugin directories for executables
- Execute with `--jn-meta`, parse JSON

**Python Plugin Discovery** (no execution):
- Parse PEP 723 `# /// script` block
- Extract `[tool.jn]` metadata via regex
- No Python execution required

#### Pattern Registry
- Specificity scoring (pattern length)
- Priority ordering (user > bundled, Zig > Python)
- Mode support checking

#### Cache System
- Store metadata in `$JN_HOME/cache/plugins.json`
- Validate with file modification times

### Exit Criteria
- [ ] Discovery finds all bundled plugins
- [ ] Discovery finds user plugins
- [ ] Python plugin metadata extracted without execution
- [ ] Cache speeds up subsequent runs

---

## Phase 7: Analysis Tools

**Goal**: Implement data analysis and discovery tools.

### Deliverables

#### jn-analyze (`tools/zig/jn-analyze/`)
Single-pass statistics:
- Record count, field frequency
- Numeric stats (min, max, mean)
- Null/missing tracking

#### jn-inspect (`tools/zig/jn-inspect/`)
Discovery and analysis:
- Profile-based endpoint discovery
- Schema inference from sample

### Exit Criteria
- [ ] `jn-analyze` produces useful statistics
- [ ] `jn-inspect` discovers profile endpoints

---

## Phase 8: Join & Merge

**Goal**: Implement multi-source data operations.

**Reference Docs**:
- [09-joining-operations.md](09-joining-operations.md)

### Deliverables

#### jn-join (`tools/zig/jn-join/`)
Hash join implementation

#### jn-merge (`tools/zig/jn-merge/`)
Source concatenation with tagging

#### jn-sh (`tools/zig/jn-sh/`)
Shell command output parsing

### Exit Criteria
- [ ] Join operations work correctly
- [ ] Merge handles multiple sources
- [ ] Shell integration parses common commands

---

## Phase 9: Orchestrator

**Goal**: Implement the main `jn` command.

### Deliverables

#### jn Command (`tools/zig/jn/`)
Thin dispatcher:
- Subcommand routing (cat → jn-cat, etc.)
- Tool discovery
- Help aggregation
- Version reporting

### Exit Criteria
- [ ] `jn cat file.csv` works
- [ ] `jn --help` shows all commands
- [ ] `jn --version` reports correctly

---

## Phase 10: Extended Formats

**Goal**: Add Zig implementations for additional formats.

### Deliverables

#### YAML Plugin (`plugins/zig/yaml/`)
- Evaluate zig-yaml library
- Read/write support

#### TOML Plugin (`plugins/zig/toml/`)
- TOML parser
- Read/write support

### Python Fallbacks (Stay in Python)
- xlsx (openpyxl)
- xml (lxml)
- gmail (Google APIs)
- mcp (Model Context Protocol)
- duckdb (database bindings)

### Exit Criteria
- [ ] YAML plugin works
- [ ] TOML plugin works
- [ ] Python plugins still function

---

## Phase 11: Testing & Migration

**Goal**: Comprehensive testing and smooth migration.

### Deliverables

#### Test Infrastructure
- Unit tests for all libraries
- Integration tests (stdin → tool → stdout)
- End-to-end pipeline tests
- Performance benchmarks vs Python

#### Python Compatibility
- Thin Python wrapper for backwards compatibility
- Deprecation warnings for changed features

#### Documentation
- Update CLAUDE.md with final architecture
- Tool man pages
- Plugin development guide

### Exit Criteria
- [ ] All tests pass
- [ ] Performance targets met
- [ ] Documentation complete

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
| OpenDAL C library build | Already prototyped, vendor/ has source |
| Zig 0.15 API changes | Pin version, use -fllvm for compatibility |
| Cross-platform builds | CI matrix with Linux, macOS, Windows |
| User migration friction | Python compatibility layer, gradual rollout |

---

## Key Documents

| Document | Purpose |
|----------|---------|
| [01-vision.md](01-vision.md) | Philosophy and design principles |
| [02-architecture.md](02-architecture.md) | Component model |
| [03-users-guide.md](03-users-guide.md) | CLI usage |
| [04-project-layout.md](04-project-layout.md) | Repository structure |
| [05-plugin-system.md](05-plugin-system.md) | Plugin interface |
| [06-matching-resolution.md](06-matching-resolution.md) | Address parsing |
| [07-profiles.md](07-profiles.md) | Hierarchical profiles |
| [08-streaming-backpressure.md](08-streaming-backpressure.md) | I/O patterns |
| [09-joining-operations.md](09-joining-operations.md) | Join/merge |
| [10-python-plugins.md](10-python-plugins.md) | PEP 723 plugins |
| [opendal-analysis.md](opendal-analysis.md) | OpenDAL integration |
| [zig-libraries-evaluation.md](zig-libraries-evaluation.md) | Library recommendations |
