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

### Target State (Zig Core + Python Extensibility)

```
jn (thin Zig orchestrator)
├── jn-cat     (source reader)
├── jn-put     (destination writer)
├── jn-filter  (ZQ wrapper / direct exec)
├── jn-head    (stream truncation)
├── jn-tail    (stream truncation)
├── jn-inspect (discovery/analysis)
├── jn-analyze (statistics)
├── jn-table   (pretty print)
│
├── plugins/zig/        # Bundled high-performance plugins
│   ├── csv     (format)
│   ├── json    (format)
│   ├── jsonl   (format)
│   ├── gz      (compression)
│   └── http    (protocol)
│
└── plugins/python/     # User-extensible Python plugins (PEP 723)
    ├── xlsx_.py        (complex formats)
    ├── parquet_.py     (ecosystem libraries)
    └── custom_.py      (user plugins)
```

**All tools share**:
- `libjn-core` - Streaming I/O, JSON handling, error patterns
- `libjn-cli` - Argument parsing, help generation
- `libjn-plugin` - Plugin interface, discovery

**Python plugins remain supported** for:
- User extensibility (custom protocols, formats)
- Complex formats requiring Python libraries (xlsx, parquet)
- Rapid prototyping before Zig implementation

---

## Features NOT Being Migrated (Deferred to Python Plugins)

### Explicitly Deferred Protocols

| Feature | Reason | Python Plugin |
|---------|--------|---------------|
| **Gmail** | OAuth2 complexity, Google API libraries | `gmail_.py` |
| **MCP** | Model Context Protocol, evolving spec | `mcp_.py` |
| **DuckDB** | SQL database, complex library binding | `duckdb_.py` |

### Explicitly Deferred Formats

| Feature | Reason | Python Plugin |
|---------|--------|---------------|
| **XLSX** | Complex ZIP + XML, requires openpyxl | `xlsx_.py` |
| **Parquet** | Binary columnar format, requires pyarrow | User plugin |
| **Avro** | Binary format, requires fastavro | User plugin |
| **XML** | Complex parsing, many edge cases | `xml_.py` |

### Explicitly Deferred Commands

| Feature | Reason | Status |
|---------|--------|--------|
| **jn check** | Python-specific AST checker, obsolete for Zig | **Deprecate entirely** |
| **jn vd** | VisiData integration, Python TUI | Keep as Python wrapper |
| **jn plugin test** | Plugin testing framework | Defer to later phase |

### Explicitly Deferred Profile Types

| Profile Type | Reason | Status |
|--------------|--------|--------|
| **Gmail profiles** | Tied to gmail_.py plugin | Keep in Python |
| **MCP profiles** | Tied to mcp_.py plugin | Keep in Python |
| **DuckDB profiles** | Tied to duckdb_.py plugin | Keep in Python |

### Features That May Never Migrate

| Feature | Reason |
|---------|--------|
| **Python plugin checker** | Zig plugins don't need it; backpressure violations impossible |
| **OAuth2 flows** | Complex browser-based auth better in Python |
| **Rich TUI output** | VisiData, interactive prompts stay Python |

### Migration Strategy for Deferred Features

1. **Keep Python plugins functional** - They work via `uv run --script`
2. **Zig discovery supports Python** - PEP 723 parsing without execution
3. **Priority ordering** - Zig plugins preferred when available
4. **Fallback chain** - Zig read → Python write (e.g., JSON indent)

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

**Python equivalent**: `src/jn/profiles/` (1,202 lines total)

### 4.1 Profile Directory Resolution
- [ ] Create `libs/zig/jn-profile/dirs.zig`
- [ ] Implement search path discovery
  - [ ] Project: `.jn/profiles` (walk up from cwd)
  - [ ] User: `~/.local/jn/profiles`
  - [ ] System: `$JN_HOME/profiles`
- [ ] Implement priority ordering (project > user > system)
- [ ] Type subdirectory mapping (http/, zq/, etc.)

### 4.2 Profile Loading
- [ ] Create `libs/zig/jn-profile/loader.zig`
- [ ] Implement JSON file loading
- [ ] Implement hierarchical merge (`_meta.json` + `endpoint.json`)
- [ ] Implement deep merge for nested objects
- [ ] Handle missing optional files gracefully

### 4.3 Environment Variable Substitution
- [ ] Create `libs/zig/jn-profile/env.zig`
- [ ] Implement `${VAR}` pattern detection
- [ ] Implement recursive substitution (nested objects/arrays)
- [ ] Implement default value syntax `${VAR:-default}`
- [ ] Error on missing required variables
- [ ] Security: Don't log/expose resolved secrets

### 4.4 Profile Reference Parsing
- [ ] Create `libs/zig/jn-profile/reference.zig`
- [ ] Parse `@namespace/name` syntax
- [ ] Parse `@namespace/name?param=value` with query params
- [ ] Map namespace to profile type directory
- [ ] Extract and validate parameters

### 4.5 HTTP Profile Support
- [ ] Create `libs/zig/jn-profile/http.zig`
- [ ] Load `_meta.json` for base config:
  ```json
  {"base_url": "https://api.example.com", "headers": {"Authorization": "Bearer ${TOKEN}"}}
  ```
- [ ] Load `endpoint.json` for specific endpoint:
  ```json
  {"path": "/v1/users", "method": "GET", "params": ["limit", "offset"]}
  ```
- [ ] Merge: base_url + path → full URL
- [ ] Merge: headers with env var substitution
- [ ] Validate provided params against allowed list
- [ ] Return: (url, headers, method)

### 4.6 ZQ Filter Profile Support
- [ ] Create `libs/zig/jn-profile/zq.zig`
- [ ] Scan `profiles/zq/**/*.{zq,jq}` files
- [ ] Extract description from first `#` comment
- [ ] Extract parameters from `# Parameters: x, y, z` line
- [ ] Fallback: detect `$param` references in content
- [ ] Parameter substitution:
  - [ ] Numeric values: unquoted (for comparisons)
  - [ ] String values: quoted (for equality)
- [ ] Strip `#` comment lines from output
- [ ] Collapse multi-line to single line

### 4.7 Profile CLI Tool (jn-profile)
- [ ] Create `tools/zig/jn-profile/main.zig`

#### 4.7.1 List Subcommand
- [ ] `jn profile list [query]` - List/search profiles
- [ ] `--type {http,zq}` filter by type
- [ ] `--format {text,json}` output format
- [ ] Group output by type and namespace

#### 4.7.2 Info Subcommand
- [ ] `jn profile info @namespace/name` - Show details
- [ ] Display: path, description, parameters, examples
- [ ] Auto-generate usage examples
- [ ] `--format {text,json}` output format

#### 4.7.3 Tree Subcommand
- [ ] `jn profile tree` - Hierarchical view
- [ ] `--type {http,zq}` filter
- [ ] ASCII tree structure

### 4.8 Profile Discovery Service
- [ ] Create `libs/zig/jn-profile/discovery.zig`
- [ ] Scan all profile directories
- [ ] Build ProfileInfo records:
  ```zig
  const ProfileInfo = struct {
      reference: []const u8,    // "@namespace/name"
      profile_type: []const u8, // "http", "zq"
      namespace: []const u8,
      name: []const u8,
      path: []const u8,
      description: []const u8,
      params: []const []const u8,
  };
  ```
- [ ] Cache discovery results
- [ ] Support search/filter operations

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

## Phase 8: Plugin Discovery Service (Polyglot)

### 8.1 Plugin Directory Structure
```
Plugin Search Order (highest to lowest priority):
1. ~/.local/jn/plugins/zig/      # User Zig plugins
2. ~/.local/jn/plugins/python/   # User Python plugins
3. .jn/plugins/                   # Project plugins (walk up)
4. $JN_HOME/plugins/zig/          # Bundled Zig plugins
5. $JN_HOME/plugins/python/       # Bundled Python plugins
```

### 8.2 Zig Plugin Discovery
- [ ] Create `libs/zig/jn-discovery/zig_plugins.zig`
- [ ] Scan for executable binaries
- [ ] Execute each with `--jn-meta`
- [ ] Parse JSON metadata response
- [ ] Store: path, matches, modes, role

### 8.3 Python Plugin Discovery (PEP 723)
- [ ] Create `libs/zig/jn-discovery/python_plugins.zig`
- [ ] Scan for `*.py` files with UV shebang
- [ ] Parse PEP 723 block without executing Python
  ```zig
  // Extract # /// script ... # /// block
  // Parse [tool.jn] section for matches, modes, role
  ```
- [ ] Validate required fields (matches, at minimum)
- [ ] Store: path, matches, modes, role, dependencies

### 8.4 Python Plugin Execution
- [ ] Create `libs/zig/jn-discovery/python_exec.zig`
- [ ] Build UV command: `uv run --quiet --script {path} --mode={mode}`
- [ ] Pass config args as CLI flags
- [ ] Spawn as child process with pipe I/O
- [ ] Handle UV not installed error gracefully

### 8.5 Caching
- [ ] Create `libs/zig/jn-discovery/cache.zig`
- [ ] Store metadata in JSON cache file
- [ ] Validate cache with mtime checks
- [ ] Separate cache entries for Zig vs Python
- [ ] Incremental cache updates

### 8.6 Pattern Registry
- [ ] Create `libs/zig/jn-discovery/registry.zig`
- [ ] Compile regex patterns from all plugins
- [ ] Implement match by source path
- [ ] Priority ordering:
  - [ ] User plugins > bundled plugins
  - [ ] Zig plugins > Python plugins (same priority level)
  - [ ] Longer patterns > shorter patterns (specificity)

### 8.7 Plugin Selection with Mode Support
- [ ] When plugin.modes is null → supports all modes (Python default)
- [ ] When plugin.modes is set → check if requested mode supported
- [ ] Fallback chain: Zig read-only → Python for write mode

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

## Phase 11: Join and Merge Commands

### 11.1 jn-join (Hash Join with Aggregations)

**Python equivalent**: `src/jn/cli/commands/join.py` (405 lines)

**Architecture**: Right source buffered in memory, left source streams

#### 11.1.1 Basic Infrastructure
- [ ] Create `tools/zig/jn-join/main.zig`
- [ ] Implement hash map for right source lookup
- [ ] Stream left source from stdin
- [ ] Output joined records to stdout

#### 11.1.2 Join Key Modes
- [ ] Natural join: `--on field` (same field name both sides)
- [ ] Named join: `--left-key X --right-key Y` (different names)
- [ ] Composite keys: `--on field1,field2` (multiple fields)

#### 11.1.3 Join Types
- [ ] Left join (default): All left records, nulls for no match
- [ ] Inner join (`--inner`): Only records with matches
- [ ] Outer join consideration (may defer - requires buffering both sides)

#### 11.1.4 Range/Condition Joins
- [ ] `--where` expression for condition-based matching
- [ ] Expression evaluation: `.line >= .start_line and .line <= .end_line`
- [ ] Secure expression parser (no eval, whitelist operators)
- [ ] Access both left (`.field`) and right (`$field` or context) values

#### 11.1.5 Output Modes
- [ ] Embed as array: `--target field` → matches embedded as array
  ```json
  {"id": 1, "orders": [{"order_id": "O1"}, {"order_id": "O2"}]}
  ```
- [ ] Flatten single match: `--flatten` → merge fields directly
- [ ] Field selection: `--pick field1,field2` → only include specific right fields

#### 11.1.6 Aggregation Functions
- [ ] `--agg "name: func(.field), ..."` syntax
- [ ] Implement aggregators:
  - [ ] `count` - Number of matches
  - [ ] `sum(.field)` - Sum of numeric values
  - [ ] `avg(.field)` - Average
  - [ ] `min(.field)` - Minimum
  - [ ] `max(.field)` - Maximum
- [ ] Expression parser for aggregation specs

#### 11.1.7 Right Source Loading
- [ ] Spawn `jn-cat` to read right source (any format/protocol)
- [ ] Build hash map from right records
- [ ] Memory limit consideration (warn if exceeds threshold)

### 11.2 jn-merge (Multi-Source Combination)

**Python equivalent**: `src/jn/cli/commands/merge.py` (154 lines)

#### 11.2.1 Basic Infrastructure
- [ ] Create `tools/zig/jn-merge/main.zig`
- [ ] Accept multiple source arguments
- [ ] Process sources sequentially

#### 11.2.2 Source Specification
- [ ] Parse `source:label=CustomLabel` syntax
- [ ] Default label to source address if not specified
- [ ] Support all source types (files, URLs, profiles)

#### 11.2.3 Source Tagging
- [ ] Inject `_source` field with source address
- [ ] Inject `_label` field with custom or default label
- [ ] Configurable field names: `--source-field`, `--label-field`

#### 11.2.4 Error Handling
- [ ] Fail-safe mode (default): Skip failed sources, continue
- [ ] Fail-fast mode (`--fail-fast`): Stop on first error
- [ ] Per-source error reporting

#### 11.2.5 Source Execution
- [ ] Spawn `jn-cat` for each source
- [ ] Stream output with metadata injection
- [ ] Handle subprocess errors gracefully

### 11.3 jn-sh (Shell Integration)

**Python equivalent**: `src/jn/cli/commands/sh.py` (163 lines)

#### 11.3.1 Basic Infrastructure
- [ ] Create `tools/zig/jn-sh/main.zig`
- [ ] Execute shell command via `/bin/sh -c`
- [ ] Capture stdout

#### 11.3.2 Output Parsing
- [ ] Detect command type for parser selection
- [ ] Implement common parsers:
  - [ ] `ls` → file objects
  - [ ] `ps` → process objects
  - [ ] `df` → disk usage objects
  - [ ] `env` → key-value objects
- [ ] Fallback: line-by-line with `_line` field

#### 11.3.3 jc Integration (Optional)
- [ ] Check if `jc` available in PATH
- [ ] Delegate to `jc` for 70+ supported commands
- [ ] Parse jc JSON output

#### 11.3.4 Error Handling
- [ ] Capture stderr
- [ ] Propagate exit codes
- [ ] Error records with `_error` field

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

| Phase | Effort | Cumulative | Notes |
|-------|--------|------------|-------|
| Phase 0: Prep | 1 day | 1 day | Cleanup, inventory |
| Phase 1: Foundation | 1 week | 1.5 weeks | libjn-core, libjn-cli, libjn-plugin |
| Phase 2: Plugin Refactor | 3 days | 2 weeks | Refactor existing Zig plugins |
| Phase 3: Address Parser | 3 days | 2.5 weeks | Universal addressing |
| Phase 4: Profiles | 1 week | 3.5 weeks | HTTP + ZQ profiles, CLI tool |
| Phase 5: Core CLI | 1 week | 4.5 weeks | cat, put, filter, head, tail |
| Phase 6: HTTP | 4 days | 5 weeks | HTTP protocol plugin |
| Phase 7: Analysis | 4 days | 5.5 weeks | inspect, analyze, table |
| Phase 8: Discovery | 4 days | 6 weeks | Polyglot plugin discovery |
| Phase 9: Orchestrator | 2 days | 6.5 weeks | jn command dispatcher |
| Phase 10: Extended Formats | 1 week | 7.5 weeks | YAML, TOML, Markdown |
| Phase 11: Join/Merge/Sh | 1.5 weeks | 9 weeks | High-value data commands |
| Phase 12: Testing | 1 week | 10 weeks | Unit, integration, benchmarks |
| Phase 13: Migration | 1 week | 11 weeks | Compatibility, rollout |

**Total**: ~11 weeks (2.75 months) of focused effort

### Priority Order (if time-constrained)

**Must Have** (Phases 0-5, 8-9): ~6.5 weeks
- Foundation libraries
- Core commands (cat, put, filter, head, tail)
- Plugin discovery (Zig + Python)
- Orchestrator

**Should Have** (Phases 4, 6-7, 11): ~3.5 weeks
- Full profile system
- HTTP protocol
- Analysis tools
- Join/Merge commands

**Nice to Have** (Phases 10, 12-13): ~3 weeks
- Extended format plugins
- Comprehensive testing
- Migration tooling

---

## Next Steps

1. Review and approve this plan
2. Start Phase 0 (cleanup and preparation)
3. Begin Phase 1 with `libjn-core` streaming library
4. Iterate with frequent testing and benchmarking
