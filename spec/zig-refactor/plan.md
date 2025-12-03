# JN Zig Refactor: Implementation Plan

> **Vision**: A pure Zig ETL toolkit where each command is an independent process that composes via Unix pipes with OS-managed backpressure.

---

## Architecture Overview

### Current State (Python)

```
Python CLI (jn) → Click commands → subprocess.Popen → Python plugins
                                                    ↘ Zig plugins (csv, json, jsonl, gz)
                                                    ↘ ZQ binary (filter)
```

**Problems**:
- Python startup overhead (~50-100ms per command)
- Complex plugin discovery/resolution in Python
- Mixed Python/Zig creates friction
- Python checker is obsolete for Zig plugins

### Target State (Pure Zig)

```
jn (thin orchestrator)
├── jn-cat     (source reader)
├── jn-put     (destination writer)
├── jn-filter  (ZQ wrapper / direct exec)
├── jn-head    (stream truncation)
├── jn-tail    (stream truncation)
├── jn-inspect (discovery/analysis)
├── jn-analyze (statistics)
├── jn-table   (pretty print)
└── plugins/
    ├── csv     (format)
    ├── json    (format)
    ├── jsonl   (format)
    ├── gz      (compression)
    ├── http    (protocol)
    └── ...
```

**All tools share**:
- `libjn-core` - Streaming I/O, JSON handling, error patterns
- `libjn-cli` - Argument parsing, help generation
- `libjn-plugin` - Plugin interface, discovery

---

## Phase 0: Preparation and Cleanup

### 0.1 Deprecate Python Plugin Checker
- [ ] Move `src/jn/checker/` to `src/jn/_deprecated/checker/`
- [ ] Remove `jn check` command from CLI
- [ ] Update `spec/done/plugin-checker.md` → `spec/deprecated/plugin-checker.md`
- [ ] Remove `.jncheck.toml` if exists
- [ ] Update CLAUDE.md to remove checker references

### 0.2 Inventory Existing Zig Code
- [ ] Document current Zig plugins (csv, json, jsonl, gz)
- [ ] Document ZQ filter engine
- [ ] Identify boilerplate patterns (quantify ~200 lines/plugin)
- [ ] Identify shared code candidates

### 0.3 Set Up New Directory Structure
- [ ] Create `libs/zig/` for shared libraries
- [ ] Create `tools/zig/` for CLI tools
- [ ] Keep `plugins/zig/` for format/protocol plugins
- [ ] Create unified `build.zig` at repo root

---

## Phase 1: Foundation Libraries

### 1.1 libjn-core: Streaming Library

**Goal**: Eliminate 200+ lines of boilerplate per plugin

#### 1.1.1 Buffered I/O Module
- [ ] Create `libs/zig/jn-core/io.zig`
- [ ] Implement `BufferedReader` struct
  - [ ] 64KB stdin buffer (configurable)
  - [ ] Zig version-compatible `readLine()` function
  - [ ] EOF detection
  - [ ] Partial line handling
- [ ] Implement `BufferedWriter` struct
  - [ ] 8KB stdout buffer (configurable)
  - [ ] `writeLine()` with newline
  - [ ] `flush()` on completion
- [ ] Add unit tests

#### 1.1.2 JSON Utilities Module
- [ ] Create `libs/zig/jn-core/json.zig`
- [ ] Implement `ArenaJsonParser`
  - [ ] Per-line arena reset pattern
  - [ ] Configurable max depth
  - [ ] Error recovery modes (skip vs fail)
- [ ] Implement `JsonWriter`
  - [ ] Compact serialization
  - [ ] Proper escaping (quotes, control chars, unicode)
  - [ ] NaN/Inf → null conversion
- [ ] Add unit tests

#### 1.1.3 Error Handling Module
- [ ] Create `libs/zig/jn-core/errors.zig`
- [ ] Define `JnError` enum (common errors)
- [ ] Implement `reportError()` for stderr
- [ ] Define exit code conventions
- [ ] Add color output (when tty detected)

#### 1.1.4 Main Loop Pattern
- [ ] Create `libs/zig/jn-core/loop.zig`
- [ ] Implement `StreamProcessor` pattern
  ```zig
  pub fn processLines(
      reader: *BufferedReader,
      writer: *BufferedWriter,
      processor: fn ([]const u8) ?[]const u8,
  ) !void
  ```
- [ ] Add SIGPIPE handling
- [ ] Add graceful shutdown

### 1.2 libjn-cli: Argument Parser

**Goal**: Consistent CLI interface across all tools

#### 1.2.1 Base Arguments
- [ ] Create `libs/zig/jn-cli/args.zig`
- [ ] Define `BaseArgs` struct
  ```zig
  const BaseArgs = struct {
      mode: Mode,        // read, write, raw, filter
      jn_meta: bool,     // Output metadata JSON
      help: bool,
      version: bool,
  };
  ```
- [ ] Implement parser for base args
- [ ] Add unit tests

#### 1.2.2 Custom Arguments
- [ ] Create argument registration API
  ```zig
  pub fn addArg(comptime T: type, name: []const u8, default: ?T) void
  ```
- [ ] Support types: string, int, bool, enum
- [ ] Implement `--key=value` and `--key value` forms
- [ ] Implement `-k value` short form

#### 1.2.3 Help Generation
- [ ] Auto-generate help from registered args
- [ ] Include description, type, default
- [ ] Format for terminal width

#### 1.2.4 Environment Variable Fallback
- [ ] `--arg` can fallback to `$JN_ARG`
- [ ] Document precedence: CLI > env > default

### 1.3 libjn-plugin: Plugin Interface

**Goal**: Standard interface for all plugins

#### 1.3.1 Plugin Metadata
- [ ] Create `libs/zig/jn-plugin/meta.zig`
- [ ] Define `PluginMeta` struct
  ```zig
  const PluginMeta = struct {
      name: []const u8,
      version: []const u8,
      matches: []const []const u8,
      role: Role,        // format, protocol, compression, filter
      modes: []const Mode,
      description: []const u8,
  };
  ```
- [ ] Implement `outputMeta()` for `--jn-meta`

#### 1.3.2 Plugin Entry Point
- [ ] Create `libs/zig/jn-plugin/main.zig`
- [ ] Implement `pluginMain()` pattern
  ```zig
  pub fn pluginMain(
      comptime meta: PluginMeta,
      comptime Handlers: type,  // struct with read/write/raw fns
  ) !void
  ```
- [ ] Handle mode dispatch
- [ ] Handle --jn-meta output
- [ ] Handle --help/--version

#### 1.3.3 Config Passing
- [ ] Create `libs/zig/jn-plugin/config.zig`
- [ ] Implement config struct builder from CLI args
- [ ] Type-safe config access

### 1.4 Build System
- [ ] Create `libs/zig/build.zig` (library build)
- [ ] Create root `build.zig` that includes libs + tools + plugins
- [ ] Add compile-time library linking
- [ ] Add cross-compilation targets
- [ ] Add `zig build test` for all tests

---

## Phase 2: Core Format Plugins (Refactor)

### 2.1 Refactor CSV Plugin to Use Libraries
- [ ] Update `plugins/zig/csv/main.zig`
- [ ] Remove duplicated streaming code (~100 lines)
- [ ] Import `jn-core` and `jn-plugin`
- [ ] Use `pluginMain()` pattern
- [ ] Verify tests still pass
- [ ] Benchmark before/after

### 2.2 Refactor JSON Plugin
- [ ] Update `plugins/zig/json/main.zig`
- [ ] Remove boilerplate
- [ ] Use shared libraries
- [ ] Add write mode (currently deferred to Python)
- [ ] Add indent configuration

### 2.3 Refactor JSONL Plugin
- [ ] Update `plugins/zig/jsonl/main.zig`
- [ ] Simplest refactor (mostly passthrough)
- [ ] Use shared libraries

### 2.4 Refactor GZ Plugin
- [ ] Update `plugins/zig/gz/main.zig`
- [ ] Keep comprezz.zig as local dependency
- [ ] Use shared libraries for I/O
- [ ] Add write mode when Zig stdlib supports it

### 2.5 Metrics After Refactor
- [ ] Document lines of code reduction per plugin
- [ ] Document compile time impact
- [ ] Document binary size impact

---

## Phase 3: Address Parsing (Zig)

### 3.1 Address Parser
- [ ] Create `libs/zig/jn-address/parser.zig`
- [ ] Implement `parseAddress()` function
  ```zig
  pub fn parseAddress(raw: []const u8) !Address
  ```
- [ ] Parse components:
  - [ ] Protocol detection (`://`)
  - [ ] Format override (`~csv`)
  - [ ] Parameters (`?key=value`)
  - [ ] Compression (`.gz`, `.bz2`, `.xz`)
  - [ ] Profile reference (`@namespace/name`)
  - [ ] Glob patterns (`*`, `**`, `?`)

### 3.2 Address Types
- [ ] Create `libs/zig/jn-address/types.zig`
- [ ] Define `Address` struct
  ```zig
  const Address = struct {
      raw: []const u8,
      base: []const u8,
      format_override: ?[]const u8,
      parameters: std.StringHashMap([]const u8),
      address_type: AddressType,
      compression: ?Compression,
  };
  ```
- [ ] Define `AddressType` enum (file, protocol, profile, glob, stdio)
- [ ] Define `Compression` enum (gz, bz2, xz)

### 3.3 Unit Tests
- [ ] Test protocol detection
- [ ] Test format override extraction
- [ ] Test parameter parsing
- [ ] Test compression detection
- [ ] Test profile reference parsing
- [ ] Test edge cases

---

## Phase 4: Profile System (Zig)

### 4.1 Profile Directory Resolution
- [ ] Create `libs/zig/jn-profile/dirs.zig`
- [ ] Implement search path discovery
  - [ ] Project: `.jn/profiles` (walk up from cwd)
  - [ ] User: `~/.local/jn/profiles`
  - [ ] System: `$JN_HOME/profiles`
- [ ] Implement priority ordering

### 4.2 Profile Loading
- [ ] Create `libs/zig/jn-profile/loader.zig`
- [ ] Implement JSON file loading
- [ ] Implement hierarchical merge (`_meta.json` + `endpoint.json`)
- [ ] Implement deep merge for nested objects

### 4.3 Environment Variable Substitution
- [ ] Create `libs/zig/jn-profile/env.zig`
- [ ] Implement `${VAR}` pattern detection
- [ ] Implement recursive substitution
- [ ] Implement default value syntax `${VAR:-default}`
- [ ] Error on missing required variables

### 4.4 Profile Reference Resolution
- [ ] Create `libs/zig/jn-profile/resolve.zig`
- [ ] Parse `@namespace/name?params`
- [ ] Map namespace to type directory
- [ ] Load and merge profile
- [ ] Substitute environment variables
- [ ] Return URL + headers (for HTTP)

### 4.5 HTTP Profile Support
- [ ] Implement HTTP-specific profile handling
- [ ] Build URL from base_url + path
- [ ] Build headers with auth substitution
- [ ] Validate parameters against allowed list

---

## Phase 5: Core CLI Tools

### 5.1 jn-cat (Universal Reader)

**Python equivalent**: `src/jn/cli/commands/cat.py` (423 lines)

#### 5.1.1 Basic File Reading
- [ ] Create `tools/zig/jn-cat/main.zig`
- [ ] Implement stdin detection (`-` or no arg)
- [ ] Implement file reading
- [ ] Pipe to format plugin based on extension

#### 5.1.2 Format Detection and Dispatch
- [ ] Implement format inference from extension
- [ ] Implement `~format` override
- [ ] Look up plugin by pattern match
- [ ] Spawn plugin subprocess with mode=read

#### 5.1.3 Glob Expansion
- [ ] Implement glob pattern detection
- [ ] Implement directory traversal
- [ ] Implement multi-file iteration
- [ ] Add source field to each record (optional)

#### 5.1.4 Compression Handling
- [ ] Detect compression from extension
- [ ] Insert decompression stage in pipeline
- [ ] Chain: file → decompress → format → stdout

#### 5.1.5 URL/Profile Handling
- [ ] Detect URL (has `://`)
- [ ] Detect profile reference (`@`)
- [ ] Resolve profile to URL + headers
- [ ] Spawn HTTP plugin with config

#### 5.1.6 Multi-Stage Pipeline
- [ ] Plan stages: protocol → decompress → format
- [ ] Spawn processes with pipe chaining
- [ ] Close stdout on reader for SIGPIPE
- [ ] Wait for all processes
- [ ] Propagate exit codes

### 5.2 jn-put (Universal Writer)

**Python equivalent**: `src/jn/cli/commands/put.py` (203 lines)

- [ ] Create `tools/zig/jn-put/main.zig`
- [ ] Implement format inference from extension
- [ ] Implement `~format` override
- [ ] Spawn plugin with mode=write
- [ ] Pipe stdin through plugin to file
- [ ] Handle stdout destination (no file arg)
- [ ] Implement compression insertion

### 5.3 jn-filter (ZQ Wrapper)

**Python equivalent**: `src/jn/cli/commands/filter.py` (205 lines)

- [ ] Create `tools/zig/jn-filter/main.zig`
- [ ] Find ZQ binary (bundled → PATH)
- [ ] Parse filter expression argument
- [ ] Resolve profile references in expression
- [ ] Exec ZQ directly (replace process, no subprocess)
- [ ] Pass through -s (slurp), -r (raw) flags

### 5.4 jn-head (First N Records)

**Python equivalent**: Part of `src/jn/cli/commands/head.py`

- [ ] Create `tools/zig/jn-head/main.zig`
- [ ] Parse `-n N` argument (default 10)
- [ ] Count lines, output first N
- [ ] Exit cleanly (triggers SIGPIPE upstream)

### 5.5 jn-tail (Last N Records)

**Python equivalent**: Part of `src/jn/cli/commands/head.py` (same file)

- [ ] Create `tools/zig/jn-tail/main.zig`
- [ ] Parse `-n N` argument (default 10)
- [ ] Implement circular buffer for last N
- [ ] Output buffer at EOF

---

## Phase 6: HTTP Protocol Plugin

### 6.1 HTTP Client Implementation
- [ ] Create `plugins/zig/http/main.zig`
- [ ] Evaluate options:
  - [ ] Option A: Zig std.http.Client (pure Zig, but limited)
  - [ ] Option B: libcurl binding (battle-tested)
  - [ ] Option C: zig-fetch (community library)
- [ ] Implement basic GET request
- [ ] Implement response streaming to stdout (raw mode)

### 6.2 HTTPS/TLS Support
- [ ] Implement TLS handshake
- [ ] Handle CA certificates (system store)
- [ ] Add `--insecure` flag for skip verification

### 6.3 Header and Auth Injection
- [ ] Accept `--header "Key: Value"` args
- [ ] Accept profile-based headers
- [ ] Implement Bearer token auth
- [ ] Implement Basic auth (base64)
- [ ] Implement API key (header or query)

### 6.4 Configuration
- [ ] Implement `--timeout` (connect + read)
- [ ] Implement `--retry` with exponential backoff
- [ ] Implement redirect following (`--max-redirects`)

---

## Phase 7: Analysis Tools

### 7.1 jn-analyze (Stream Statistics)

**Python equivalent**: `src/jn/cli/commands/analyze.py` (413 lines)

- [ ] Create `tools/zig/jn-analyze/main.zig`
- [ ] Implement single-pass statistics:
  - [ ] Record count
  - [ ] Field frequency
  - [ ] Type distribution per field
  - [ ] Numeric stats (min, max, mean, stddev)
  - [ ] String stats (min/max length)
  - [ ] Null/missing tracking
- [ ] Implement sample collection (first N, random N)
- [ ] Output as JSON or table

### 7.2 jn-inspect (Discovery and Analysis)

**Python equivalent**: `src/jn/cli/commands/inspect.py` (620 lines)

- [ ] Create `tools/zig/jn-inspect/main.zig`
- [ ] Implement profile-based endpoint discovery
- [ ] Implement schema inference from data sample
- [ ] Combine with analyze for data inspection
- [ ] Output formatting (JSON, table)

### 7.3 jn-table (Pretty Print)

**Python equivalent**: `src/jn/cli/commands/table.py` (190 lines)

- [ ] Create `tools/zig/jn-table/main.zig`
- [ ] Implement column width calculation (sample-based)
- [ ] Implement table formats:
  - [ ] Simple (spaces)
  - [ ] Grid (ASCII borders)
  - [ ] Markdown
- [ ] Detect terminal width
- [ ] Truncate wide columns
- [ ] Handle missing fields

---

## Phase 8: Plugin Discovery Service

### 8.1 Discovery Implementation
- [ ] Create `libs/zig/jn-discovery/scan.zig`
- [ ] Scan plugin directories for executables
- [ ] Execute each with `--jn-meta`
- [ ] Parse JSON metadata response
- [ ] Build pattern registry

### 8.2 Caching
- [ ] Create `libs/zig/jn-discovery/cache.zig`
- [ ] Store metadata in JSON cache file
- [ ] Validate cache with mtime checks
- [ ] Incremental cache updates

### 8.3 Pattern Matching
- [ ] Create `libs/zig/jn-discovery/registry.zig`
- [ ] Compile regex patterns
- [ ] Implement match by source path
- [ ] Implement specificity ordering
- [ ] Prefer binary plugins over Python fallback

---

## Phase 9: Orchestrator CLI

### 9.1 jn Command (Thin Wrapper)
- [ ] Create `tools/zig/jn/main.zig`
- [ ] Implement subcommand routing
  ```
  jn cat  → exec jn-cat
  jn put  → exec jn-put
  jn filter → exec jn-filter
  ...
  ```
- [ ] Pass through all arguments after subcommand
- [ ] Implement `jn --help` (aggregate from tools)
- [ ] Implement `jn --version`

### 9.2 Tool Discovery
- [ ] Scan PATH for `jn-*` binaries
- [ ] Scan `$JN_HOME/bin/` for bundled tools
- [ ] List available commands

### 9.3 Pipeline Construction
- [ ] For complex commands, build multi-tool pipeline
- [ ] Example: `jn cat data.csv.gz` →
  - Spawn `jn-cat` which spawns `gz` → `csv` plugins

---

## Phase 10: Extended Format Plugins

### 10.1 YAML Plugin
- [ ] Create `plugins/zig/yaml/main.zig`
- [ ] Evaluate YAML parser options (zig-yaml or custom)
- [ ] Implement read: YAML → NDJSON
- [ ] Implement write: NDJSON → YAML
- [ ] Handle multi-document YAML

### 10.2 TOML Plugin
- [ ] Create `plugins/zig/toml/main.zig`
- [ ] Implement TOML parser
- [ ] Implement read: TOML → NDJSON
- [ ] Implement write: NDJSON → TOML

### 10.3 Markdown Table Plugin
- [ ] Create `plugins/zig/markdown/main.zig`
- [ ] Implement Markdown table parsing
- [ ] Implement table generation from NDJSON

### 10.4 XLSX Plugin (Stretch)
- [ ] Evaluate complexity (may remain Python)
- [ ] If feasible: implement with Zig ZIP + XML parsing
- [ ] Otherwise: document as Python-only

---

## Phase 11: Advanced Commands (Stretch)

### 11.1 jn-join
- [ ] Create `tools/zig/jn-join/main.zig`
- [ ] Implement hash join on key field
- [ ] Support join types (inner, left, outer)
- [ ] Handle memory limits (spill to disk)

### 11.2 jn-merge
- [ ] Create `tools/zig/jn-merge/main.zig`
- [ ] Implement sequential merge (concatenate streams)
- [ ] Implement interleaved merge
- [ ] Add source tagging

### 11.3 jn-sh (Shell Integration)
- [ ] Create `tools/zig/jn-sh/main.zig`
- [ ] Execute shell command
- [ ] Parse output to NDJSON (via parsers or jc integration)
- [ ] Handle exit codes

---

## Phase 12: Testing and Documentation

### 12.1 Unit Tests
- [ ] Test coverage for all libraries
- [ ] Test coverage for all tools
- [ ] Test coverage for all plugins

### 12.2 Integration Tests
- [ ] End-to-end pipeline tests
- [ ] Multi-stage pipeline tests
- [ ] Error handling tests
- [ ] Backpressure verification tests

### 12.3 Performance Benchmarks
- [ ] Benchmark vs Python version
- [ ] Benchmark vs jq (for filter)
- [ ] Document memory usage
- [ ] Document startup time

### 12.4 Documentation
- [ ] Update README.md
- [ ] Update CLAUDE.md
- [ ] Write tool man pages
- [ ] Write plugin development guide
- [ ] Archive Python documentation

---

## Phase 13: Migration and Deprecation

### 13.1 Python Compatibility Layer
- [ ] Create thin Python wrapper that delegates to Zig
- [ ] Maintain backwards compatibility for existing users
- [ ] Deprecation warnings for Python-specific features

### 13.2 Gradual Rollout
- [ ] Phase 1: Ship Zig tools alongside Python (opt-in)
- [ ] Phase 2: Make Zig tools default (Python fallback)
- [ ] Phase 3: Remove Python implementation

### 13.3 Cleanup
- [ ] Remove deprecated Python code
- [ ] Remove Python plugin checker
- [ ] Archive Python specs
- [ ] Update all documentation

---

## Success Metrics

| Metric | Python Baseline | Zig Target | Improvement |
|--------|-----------------|------------|-------------|
| Startup time | 50-100ms | <5ms | 10-20x |
| Memory (10MB file) | ~50MB | ~1MB | 50x |
| Memory (1GB file) | ~500MB+ | ~1MB | 500x |
| Lines of code | 10,177 | ~5,000 | 50% |
| Binary size | N/A (Python) | ~5MB total | N/A |
| Plugin boilerplate | N/A | <50 lines | -150 lines |

---

## Risk Mitigation

### Risk 1: Zig HTTP/TLS complexity
**Mitigation**: Use libcurl binding if std.http insufficient

### Risk 2: YAML/TOML parser availability
**Mitigation**: Keep Python plugins as fallback for complex formats

### Risk 3: Cross-platform testing
**Mitigation**: CI matrix with Linux, macOS, Windows

### Risk 4: User migration friction
**Mitigation**: Python compatibility layer, gradual rollout

---

## Timeline Estimate

| Phase | Effort | Cumulative |
|-------|--------|------------|
| Phase 0: Prep | 1 day | 1 day |
| Phase 1: Foundation | 1 week | 1 week |
| Phase 2: Plugin Refactor | 3 days | 2 weeks |
| Phase 3: Address Parser | 3 days | 2 weeks |
| Phase 4: Profiles | 4 days | 3 weeks |
| Phase 5: Core CLI | 1 week | 4 weeks |
| Phase 6: HTTP | 4 days | 5 weeks |
| Phase 7: Analysis | 4 days | 5 weeks |
| Phase 8: Discovery | 3 days | 6 weeks |
| Phase 9: Orchestrator | 2 days | 6 weeks |
| Phase 10: Extended | 1 week | 7 weeks |
| Phase 11: Advanced | 1 week | 8 weeks |
| Phase 12: Testing | 1 week | 9 weeks |
| Phase 13: Migration | 1 week | 10 weeks |

**Total**: ~10 weeks (2.5 months) of focused effort

---

## Next Steps

1. Review and approve this plan
2. Start Phase 0 (cleanup and preparation)
3. Begin Phase 1 with `libjn-core` streaming library
4. Iterate with frequent testing and benchmarking
