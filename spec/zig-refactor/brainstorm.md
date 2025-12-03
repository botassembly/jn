# JN Zig Refactor: Brainstorming Document

> **Goal**: Migrate JN from Python to a pure Zig implementation, prioritizing performance and backpressure-aware streaming composition.

## Executive Summary

Current JN is ~10,177 lines of Python across 56 files. The goal is to replace this with a suite of composable Zig CLI tools that:
- Stream data with constant memory via OS pipe backpressure
- Run as independent processes that compose via Unix pipes
- Share a common library to eliminate boilerplate
- Have a thin orchestrator CLI (`jn`) that spawns the right tools

---

## Part 1: 20 Core Ideas with Dependencies

### Idea 1: Core NDJSON Streaming Library
**What**: Shared Zig library for buffered stdin/stdout, line reading, JSON parsing
**Why**: Every tool needs this; currently 200+ lines duplicated per plugin
**Dependencies**: None (foundation)
**Recursive Decomposition**:
- 1.1 Buffered I/O wrapper (64KB stdin, 8KB stdout)
- 1.2 Line reader with Zig version compatibility (0.15.1 vs 0.15.2)
- 1.3 JSON value wrapper with arena allocator lifecycle
- 1.4 NDJSON writer with proper escaping and flushing
- 1.5 Error handling patterns (skip vs fail on malformed)

### Idea 2: CLI Argument Parser Library
**What**: Shared argument parsing with `--mode`, `--jn-meta`, custom args
**Why**: Every tool parses the same base arguments plus custom ones
**Dependencies**: None (foundation)
**Recursive Decomposition**:
- 2.1 Base argument struct (mode, jn-meta, help, version)
- 2.2 Custom argument registration API
- 2.3 Type-safe argument parsing (string, int, bool, enum)
- 2.4 Help text generation from registered args
- 2.5 Environment variable fallback support

### Idea 3: Plugin Metadata System
**What**: Standardized `--jn-meta` JSON output for all tools
**Why**: Discovery system needs consistent metadata format
**Dependencies**: Idea 2 (CLI args)
**Recursive Decomposition**:
- 3.1 Metadata struct (name, version, matches, role, modes)
- 3.2 JSON serialization helper
- 3.3 Regex pattern storage format
- 3.4 Mode enumeration (read, write, raw, filter)
- 3.5 Optional capability flags (supports_container, manages_parameters)

### Idea 4: `jn-cat` - Universal Reader
**What**: Reads any source (file, stdin, URL) and outputs NDJSON
**Why**: Core command; Python version is 423 lines
**Dependencies**: Idea 1 (streaming), Idea 3 (metadata), Idea 8 (format dispatch)
**Recursive Decomposition**:
- 4.1 Source type detection (file vs stdin vs URL vs glob)
- 4.2 File reading with memory-mapped I/O option
- 4.3 Glob expansion for multi-file sources
- 4.4 Format plugin dispatch (CSV, JSON, JSONL, etc.)
- 4.5 Compression detection and decompression stage insertion
- 4.6 Multi-stage pipeline construction (protocol → decompress → format)

### Idea 5: `jn-put` - Universal Writer
**What**: Reads NDJSON from stdin, writes to any format/destination
**Why**: Core command; Python version is 203 lines
**Dependencies**: Idea 1 (streaming), Idea 3 (metadata), Idea 8 (format dispatch)
**Recursive Decomposition**:
- 5.1 Destination type detection (file vs stdout)
- 5.2 Format inference from extension or override
- 5.3 Format plugin dispatch for write mode
- 5.4 Compression detection and insertion
- 5.5 Atomic file write (temp file + rename)

### Idea 6: `jn-filter` / ZQ Integration
**What**: Filter/transform NDJSON using ZQ expressions
**Why**: Already have ZQ; need orchestration wrapper
**Dependencies**: Idea 1 (streaming), ZQ binary
**Recursive Decomposition**:
- 6.1 Expression parsing and validation
- 6.2 ZQ binary location (bundled vs PATH)
- 6.3 Direct exec to ZQ (no intermediate process)
- 6.4 Profile reference resolution for stored filters
- 6.5 Slurp mode passthrough

### Idea 7: `jn-head` / `jn-tail` - Stream Truncation
**What**: Output first/last N records from NDJSON stream
**Why**: Essential for sampling; demonstrates SIGPIPE backpressure
**Dependencies**: Idea 1 (streaming)
**Recursive Decomposition**:
- 7.1 Count-based limiting (first N lines)
- 7.2 Tail with circular buffer (last N lines, constant memory)
- 7.3 Proper SIGPIPE handling for early termination
- 7.4 Support for `-n` argument

### Idea 8: Format Plugin System
**What**: Architecture for format readers/writers (CSV, JSON, YAML, etc.)
**Why**: Need standard interface for all format handlers
**Dependencies**: Idea 1 (streaming), Idea 2 (CLI args), Idea 3 (metadata)
**Recursive Decomposition**:
- 8.1 Plugin interface (read: bytes→NDJSON, write: NDJSON→bytes)
- 8.2 Mode dispatch (--mode=read vs --mode=write)
- 8.3 Configuration passing via CLI args
- 8.4 Raw mode for byte passthrough (protocols, compression)
- 8.5 Plugin discovery via filesystem scan + --jn-meta

### Idea 9: CSV Format Plugin (Zig)
**What**: CSV/TSV reader and writer
**Why**: Most common format; already have Zig version (523 lines)
**Dependencies**: Idea 8 (format plugin system)
**Recursive Decomposition**:
- 9.1 Delimiter detection/configuration
- 9.2 Quote handling (RFC 4180 compliant)
- 9.3 Header extraction and field mapping
- 9.4 Streaming read (line by line)
- 9.5 Write with proper escaping

### Idea 10: JSON Format Plugin (Zig)
**What**: JSON array reader and pretty-print writer
**Why**: Second most common format; already have partial Zig version
**Dependencies**: Idea 8 (format plugin system)
**Recursive Decomposition**:
- 10.1 Array detection and streaming extraction
- 10.2 Object wrapping for single objects
- 10.3 Write with configurable indent
- 10.4 Large array streaming without full load

### Idea 11: JSONL Format Plugin (Zig)
**What**: NDJSON/JSONL passthrough with validation
**Why**: Native format; already have Zig version (188 lines)
**Dependencies**: Idea 8 (format plugin system)
**Recursive Decomposition**:
- 11.1 Line-by-line validation
- 11.2 Passthrough mode (skip validation for speed)
- 11.3 Error handling (skip vs fail on invalid)

### Idea 12: Compression Plugins (GZ, etc.)
**What**: Streaming compression/decompression
**Why**: Essential for real-world data; have GZ reader in Zig
**Dependencies**: Idea 8 (format plugin system)
**Recursive Decomposition**:
- 12.1 GZ decompression (using comprezz library)
- 12.2 GZ compression (when Zig stdlib supports it)
- 12.3 Format detection from magic bytes
- 12.4 Raw mode (bytes in, bytes out)

### Idea 13: HTTP Protocol Plugin
**What**: Fetch data from HTTP/HTTPS URLs
**Why**: Essential for API access; Python version uses requests
**Dependencies**: Idea 8 (format plugin system), Idea 14 (profiles)
**Recursive Decomposition**:
- 13.1 HTTP client (Zig std.http or libcurl binding)
- 13.2 HTTPS/TLS support
- 13.3 Header injection from profiles
- 13.4 Authentication (Bearer, Basic, API key)
- 13.5 Response streaming (chunked transfer)
- 13.6 Timeout and retry configuration

### Idea 14: Profile System
**What**: Hierarchical configuration for APIs and services
**Why**: Credentials and endpoint config without embedding in commands
**Dependencies**: Idea 2 (CLI args)
**Recursive Decomposition**:
- 14.1 Profile directory discovery (~/.local/jn/profiles, .jn/profiles)
- 14.2 JSON profile loading
- 14.3 Hierarchical merge (_meta.json + endpoint.json)
- 14.4 Environment variable substitution (${VAR})
- 14.5 Profile reference parsing (@namespace/name)
- 14.6 Parameter validation against profile schema

### Idea 15: Address Parser
**What**: Parse universal addresses: `source[~format][?params]`
**Why**: Core abstraction for all source/destination specifications
**Dependencies**: None (can be standalone)
**Recursive Decomposition**:
- 15.1 Protocol detection (http://, file://, etc.)
- 15.2 Format override extraction (~csv, ~json)
- 15.3 Query parameter parsing (?key=value)
- 15.4 Compression detection from extension (.gz, .bz2)
- 15.5 Profile reference detection (@namespace/name)
- 15.6 Glob pattern detection (*, **, ?)

### Idea 16: `jn-inspect` - Discovery and Analysis
**What**: Discover API endpoints, analyze data schemas
**Why**: Agent-friendly introspection; Python version is 620 lines
**Dependencies**: Idea 1 (streaming), Idea 14 (profiles)
**Recursive Decomposition**:
- 16.1 Profile-based endpoint discovery
- 16.2 Schema inference from data sample
- 16.3 Statistics collection (types, nulls, ranges)
- 16.4 Output formatting (JSON, table)

### Idea 17: `jn-analyze` - Stream Statistics
**What**: Single-pass statistics on NDJSON stream
**Why**: Useful for data exploration; Python version is 413 lines
**Dependencies**: Idea 1 (streaming)
**Recursive Decomposition**:
- 17.1 Type frequency counting
- 17.2 Numeric statistics (min, max, mean, stddev)
- 17.3 String statistics (lengths, patterns)
- 17.4 Null/missing field tracking
- 17.5 Sample collection (first N, random N)
- 17.6 Facet extraction (unique values)

### Idea 18: `jn-table` - Pretty Print
**What**: Format NDJSON as readable table
**Why**: Human-friendly output; Python uses tabulate
**Dependencies**: Idea 1 (streaming)
**Recursive Decomposition**:
- 18.1 Column width calculation (sample-based)
- 18.2 Table formatting (grid, simple, markdown)
- 18.3 Terminal width detection
- 18.4 Truncation for wide columns
- 18.5 Header extraction from first record

### Idea 19: Orchestrator CLI (`jn`)
**What**: Thin wrapper that dispatches to individual tools
**Why**: User-friendly unified interface
**Dependencies**: All tools (spawns them)
**Recursive Decomposition**:
- 19.1 Subcommand routing (cat, put, filter, head, etc.)
- 19.2 Tool discovery (which jn-* binaries exist)
- 19.3 Help aggregation from tools
- 19.4 Version reporting
- 19.5 Pipeline construction for multi-stage commands
- 19.6 Error reporting and exit code propagation

### Idea 20: Plugin Discovery Service
**What**: Scan filesystem for available plugins, cache metadata
**Why**: Need to know what formats/protocols are available
**Dependencies**: Idea 3 (metadata)
**Recursive Decomposition**:
- 20.1 Directory scanning (JN_HOME/plugins, custom dirs)
- 20.2 Binary execution for --jn-meta
- 20.3 Cache file with mtime validation
- 20.4 Pattern registry construction
- 20.5 Best-match selection (specificity + binary preference)

---

## Part 2: Dependency Graph

```
                    ┌─────────────────────────────────────┐
                    │     Foundation Layer (No deps)      │
                    └─────────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
   ┌───────────┐              ┌───────────┐              ┌───────────┐
   │  Idea 1   │              │  Idea 2   │              │  Idea 15  │
   │ Streaming │              │ CLI Args  │              │ Address   │
   │  Library  │              │  Parser   │              │  Parser   │
   └───────────┘              └───────────┘              └───────────┘
         │                           │                         │
         │                     ┌─────┴─────┐                   │
         │                     ▼           ▼                   │
         │              ┌───────────┐ ┌───────────┐            │
         │              │  Idea 3   │ │  Idea 14  │            │
         │              │ Metadata  │ │ Profiles  │            │
         │              └───────────┘ └───────────┘            │
         │                     │           │                   │
         └─────────────────────┼───────────┼───────────────────┘
                               ▼           ▼
                    ┌─────────────────────────────────────┐
                    │      Idea 8: Format Plugin System   │
                    └─────────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
   ┌───────────┐              ┌───────────┐              ┌───────────┐
   │ Idea 9-12 │              │  Idea 13  │              │  Idea 20  │
   │  Format   │              │   HTTP    │              │ Discovery │
   │  Plugins  │              │  Plugin   │              │  Service  │
   └───────────┘              └───────────┘              └───────────┘
         │                           │                         │
         └───────────────────────────┼─────────────────────────┘
                                     ▼
                    ┌─────────────────────────────────────┐
                    │     Idea 4-7: Core CLI Commands     │
                    │   (cat, put, filter, head, tail)    │
                    └─────────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
   ┌───────────┐              ┌───────────┐              ┌───────────┐
   │ Idea 16   │              │  Idea 17  │              │  Idea 18  │
   │  Inspect  │              │  Analyze  │              │   Table   │
   └───────────┘              └───────────┘              └───────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────────┐
                    │    Idea 19: Orchestrator CLI (jn)   │
                    └─────────────────────────────────────┘
```

---

## Part 3: Deep Recursive Decomposition

### Streaming Library (Idea 1) - Full Breakdown

```
1. Streaming Library
├── 1.1 Buffered I/O
│   ├── 1.1.1 stdin buffer configuration (size, allocation strategy)
│   ├── 1.1.2 stdout buffer configuration
│   ├── 1.1.3 Buffer flush semantics (auto vs explicit)
│   └── 1.1.4 Error handling on I/O failure
│
├── 1.2 Line Reader
│   ├── 1.2.1 Zig version detection (comptime)
│   ├── 1.2.2 takeDelimiter vs takeDelimiterExclusive API
│   ├── 1.2.3 EOF detection
│   ├── 1.2.4 Line length limits (configurable max)
│   └── 1.2.5 Partial line handling at buffer boundary
│
├── 1.3 JSON Value Handling
│   ├── 1.3.1 Arena allocator initialization
│   ├── 1.3.2 Per-line arena reset pattern
│   ├── 1.3.3 JSON parse options (max depth, string handling)
│   ├── 1.3.4 Parse error recovery (skip vs fail)
│   └── 1.3.5 Value type introspection helpers
│
├── 1.4 NDJSON Writer
│   ├── 1.4.1 JSON serialization (compact)
│   ├── 1.4.2 String escaping (quotes, control chars)
│   ├── 1.4.3 Number formatting (NaN/Inf → null)
│   ├── 1.4.4 Newline after each record
│   └── 1.4.5 Flush on completion
│
└── 1.5 Error Handling
    ├── 1.5.1 Error type definitions
    ├── 1.5.2 stderr message formatting
    ├── 1.5.3 Exit code conventions
    └── 1.5.4 Recoverable vs fatal errors
```

### Format Plugin System (Idea 8) - Full Breakdown

```
8. Format Plugin System
├── 8.1 Plugin Interface
│   ├── 8.1.1 Function signature for reads() → iterator
│   ├── 8.1.2 Function signature for writes() → void
│   ├── 8.1.3 Config struct passing
│   ├── 8.1.4 Error propagation pattern
│   └── 8.1.5 Cleanup/finalization hooks
│
├── 8.2 Mode Dispatch
│   ├── 8.2.1 --mode=read invocation
│   ├── 8.2.2 --mode=write invocation
│   ├── 8.2.3 --mode=raw invocation (byte passthrough)
│   ├── 8.2.4 Default mode selection
│   └── 8.2.5 Invalid mode error handling
│
├── 8.3 Configuration
│   ├── 8.3.1 CLI arg → config mapping
│   ├── 8.3.2 Type conversion (string → typed value)
│   ├── 8.3.3 Default value handling
│   ├── 8.3.4 Required parameter validation
│   └── 8.3.5 Unknown parameter warnings
│
├── 8.4 Raw Mode
│   ├── 8.4.1 Byte-level stdin reading
│   ├── 8.4.2 Byte-level stdout writing
│   ├── 8.4.3 No JSON parsing/validation
│   └── 8.4.4 Used by protocols and compression
│
└── 8.5 Plugin Discovery
    ├── 8.5.1 Executable detection in plugin dirs
    ├── 8.5.2 --jn-meta invocation and parsing
    ├── 8.5.3 Pattern → plugin mapping
    ├── 8.5.4 Priority ordering (binary > Python fallback)
    └── 8.5.5 Cache invalidation on mtime change
```

### jn-cat Command (Idea 4) - Full Breakdown

```
4. jn-cat Command
├── 4.1 Source Detection
│   ├── 4.1.1 Stdin detection (- or no arg)
│   ├── 4.1.2 File path validation
│   ├── 4.1.3 URL detection (has ://)
│   ├── 4.1.4 Profile reference detection (@)
│   ├── 4.1.5 Glob pattern detection (*, **, ?)
│   └── 4.1.6 Address parsing (format override, params)
│
├── 4.2 File Reading
│   ├── 4.2.1 Open file handle
│   ├── 4.2.2 Memory-mapped option for large files
│   ├── 4.2.3 Stream to plugin stdin
│   └── 4.2.4 Error handling (not found, permission)
│
├── 4.3 Glob Expansion
│   ├── 4.3.1 Pattern parsing
│   ├── 4.3.2 Directory traversal
│   ├── 4.3.3 Match filtering
│   ├── 4.3.4 Multi-file iteration
│   └── 4.3.5 File metadata injection (source field)
│
├── 4.4 Format Dispatch
│   ├── 4.4.1 Format inference from extension
│   ├── 4.4.2 Format override from ~hint
│   ├── 4.4.3 Plugin lookup by pattern
│   ├── 4.4.4 Spawn plugin process
│   └── 4.4.5 Pipe connection (file → plugin → stdout)
│
├── 4.5 Compression Handling
│   ├── 4.5.1 Extension detection (.gz, .bz2, .xz)
│   ├── 4.5.2 Magic byte detection (optional)
│   ├── 4.5.3 Insert decompression stage
│   └── 4.5.4 Chain: source → decompress → format → stdout
│
└── 4.6 Multi-Stage Pipeline
    ├── 4.6.1 Stage planning (1, 2, or 3 stages)
    ├── 4.6.2 Process spawning with pipe chaining
    ├── 4.6.3 stdout.close() for SIGPIPE backpressure
    ├── 4.6.4 Wait for all processes
    └── 4.6.5 Exit code propagation
```

### HTTP Protocol Plugin (Idea 13) - Full Breakdown

```
13. HTTP Protocol Plugin
├── 13.1 HTTP Client
│   ├── 13.1.1 Zig std.http.Client setup
│   ├── 13.1.2 Connection pooling consideration
│   ├── 13.1.3 Request building (method, URL, headers)
│   ├── 13.1.4 Response handling
│   └── 13.1.5 Error mapping (network, HTTP status)
│
├── 13.2 TLS Support
│   ├── 13.2.1 Certificate handling
│   ├── 13.2.2 CA bundle location
│   ├── 13.2.3 Skip verification option (dangerous)
│   └── 13.2.4 SNI configuration
│
├── 13.3 Header Injection
│   ├── 13.3.1 Profile-based headers
│   ├── 13.3.2 CLI-specified headers
│   ├── 13.3.3 Default headers (User-Agent, Accept)
│   └── 13.3.4 Header merging (CLI overrides profile)
│
├── 13.4 Authentication
│   ├── 13.4.1 Bearer token (Authorization: Bearer xxx)
│   ├── 13.4.2 Basic auth (base64 encoded)
│   ├── 13.4.3 API key (header or query param)
│   ├── 13.4.4 OAuth2 token refresh (stretch goal)
│   └── 13.4.5 Credential resolution from env vars
│
├── 13.5 Response Streaming
│   ├── 13.5.1 Chunked transfer decoding
│   ├── 13.5.2 Content-Length handling
│   ├── 13.5.3 Stream to stdout (raw mode)
│   ├── 13.5.4 Backpressure via pipe buffer
│   └── 13.5.5 Partial response on SIGPIPE
│
└── 13.6 Configuration
    ├── 13.6.1 Timeout (connect, read)
    ├── 13.6.2 Retry count and backoff
    ├── 13.6.3 Redirect following (max hops)
    └── 13.6.4 Proxy support (stretch goal)
```

### Profile System (Idea 14) - Full Breakdown

```
14. Profile System
├── 14.1 Directory Discovery
│   ├── 14.1.1 ~/.local/jn/profiles (user)
│   ├── 14.1.2 .jn/profiles (project, walk up)
│   ├── 14.1.3 $JN_HOME/profiles (bundled)
│   ├── 14.1.4 Priority ordering (project > user > bundled)
│   └── 14.1.5 Type subdirectories (http/, zq/, mcp/)
│
├── 14.2 JSON Loading
│   ├── 14.2.1 File reading
│   ├── 14.2.2 JSON parsing
│   ├── 14.2.3 Schema validation (optional)
│   └── 14.2.4 Error reporting (file, line, message)
│
├── 14.3 Hierarchical Merge
│   ├── 14.3.1 _meta.json as base config
│   ├── 14.3.2 endpoint.json as overlay
│   ├── 14.3.3 Deep merge for nested objects
│   ├── 14.3.4 Array handling (replace vs append)
│   └── 14.3.5 Inheritance chain (multiple _meta.json levels)
│
├── 14.4 Environment Variables
│   ├── 14.4.1 ${VAR} pattern detection
│   ├── 14.4.2 Environment lookup
│   ├── 14.4.3 Missing variable error
│   ├── 14.4.4 Default value syntax ${VAR:-default}
│   └── 14.4.5 Recursive substitution in nested structures
│
├── 14.5 Reference Parsing
│   ├── 14.5.1 @namespace/name syntax
│   ├── 14.5.2 @namespace/name?params syntax
│   ├── 14.5.3 Namespace → type mapping (http, zq, mcp)
│   ├── 14.5.4 Parameter extraction
│   └── 14.5.5 Validation against profile's allowed params
│
└── 14.6 Parameter Validation
    ├── 14.6.1 Profile schema definition
    ├── 14.6.2 Type checking
    ├── 14.6.3 Required vs optional
    ├── 14.6.4 Default value injection
    └── 14.6.5 Unknown parameter warning
```

---

## Part 4: Additional Ideas (21-30)

### Idea 21: Build System
**What**: Unified build for all Zig tools with shared library linking
**Dependencies**: All Zig code
**Decomposition**:
- 21.1 Monorepo structure (libs/, tools/, plugins/)
- 21.2 Shared library compilation
- 21.3 Tool binary compilation with library linking
- 21.4 Cross-compilation targets (linux, macos, windows)
- 21.5 Release packaging (tar.gz with all binaries)

### Idea 22: Test Infrastructure
**What**: Unit and integration testing framework
**Dependencies**: All tools
**Decomposition**:
- 22.1 Unit tests per module
- 22.2 Integration tests (stdin → tool → stdout)
- 22.3 Fixture data management
- 22.4 CI/CD pipeline
- 22.5 Coverage reporting

### Idea 23: Error Messages and UX
**What**: Consistent, helpful error messages across all tools
**Dependencies**: Idea 1 (streaming library)
**Decomposition**:
- 23.1 Error code enumeration
- 23.2 Message templates with context
- 23.3 Suggestions for common mistakes
- 23.4 Color output (when tty)
- 23.5 Verbose mode for debugging

### Idea 24: YAML Format Plugin
**What**: YAML reader and writer
**Dependencies**: Idea 8 (format system)
**Decomposition**:
- 24.1 YAML parser (zig-yaml or custom)
- 24.2 Multi-document support
- 24.3 YAML → JSON conversion
- 24.4 JSON → YAML pretty print

### Idea 25: TOML Format Plugin
**What**: TOML reader and writer
**Dependencies**: Idea 8 (format system)
**Decomposition**:
- 25.1 TOML parser
- 25.2 TOML → JSON conversion
- 25.3 Table array handling

### Idea 26: Markdown Table Plugin
**What**: Markdown table reader and writer
**Dependencies**: Idea 8 (format system)
**Decomposition**:
- 26.1 Markdown table parsing
- 26.2 Table generation from NDJSON
- 26.3 Alignment handling

### Idea 27: `jn-join` - Stream Join
**What**: Join two NDJSON streams on a key
**Dependencies**: Idea 1 (streaming)
**Decomposition**:
- 27.1 Hash join implementation
- 27.2 Memory-bounded join (spill to disk)
- 27.3 Join types (inner, left, outer)
- 27.4 Multi-key join

### Idea 28: `jn-merge` - Stream Merge
**What**: Merge multiple NDJSON streams
**Dependencies**: Idea 1 (streaming)
**Decomposition**:
- 28.1 Sequential merge (cat-like)
- 28.2 Interleaved merge
- 28.3 Source tagging

### Idea 29: Shell Command Integration (`jn-sh`)
**What**: Execute shell commands and parse output to NDJSON
**Dependencies**: Idea 1 (streaming)
**Decomposition**:
- 29.1 Command execution
- 29.2 Output parsing (JSON, tabular, custom)
- 29.3 jc integration or replacement
- 29.4 Error handling (exit codes)

### Idea 30: VisiData Integration (`jn-vd`)
**What**: Pipe NDJSON to VisiData for interactive exploration
**Dependencies**: Idea 1 (streaming)
**Decomposition**:
- 30.1 Temp file creation
- 30.2 VisiData spawning
- 30.3 Interactive mode detection
- 30.4 Result capture

---

## Part 5: What Stays in Python (Compatibility Layer)

Some features may remain in Python for pragmatic reasons:

1. **Complex API clients** (Gmail OAuth, MCP) - Python has better library support
2. **xlsx format** - Requires complex library (not worth Zig port initially)
3. **Plugin development** - Keep Python plugin support for rapid prototyping
4. **Backwards compatibility** - Thin Python wrapper that delegates to Zig binaries

The Python layer becomes optional, only needed for:
- Legacy plugins
- Complex authentication flows
- Formats without Zig libraries

---

## Part 6: Line Count Comparison

| Component | Python Lines | Zig Estimate | Reduction |
|-----------|-------------|--------------|-----------|
| Streaming + CLI (shared) | 0 (duplicated) | 400 | -200/plugin |
| cat | 423 | 300 | 29% |
| put | 203 | 200 | 1% |
| filter | 205 | 100 | 51% |
| head/tail | 191 | 150 | 21% |
| inspect | 620 | 400 | 35% |
| analyze | 413 | 350 | 15% |
| table | 190 | 200 | -5% |
| addressing | 1,338 | 600 | 55% |
| profiles | 1,202 | 500 | 58% |
| plugins/discovery | 697 | 300 | 57% |
| **Total Core** | **5,482** | **3,500** | **36%** |

**Note**: Zig is more verbose for some things (error handling), less verbose for others (no class boilerplate). Net reduction expected from eliminating Python framework overhead.

---

## Summary

This brainstorming identifies **30 distinct ideas** with full dependency mapping and recursive decomposition. The migration path is:

1. **Foundation** (Ideas 1-3): Shared libraries for streaming, CLI, metadata
2. **Plugin System** (Idea 8): Standard interface for all format/protocol handlers
3. **Core Commands** (Ideas 4-7): cat, put, filter, head, tail
4. **Format Plugins** (Ideas 9-12): CSV, JSON, JSONL, compression
5. **Protocol Plugins** (Ideas 13-14): HTTP with profiles
6. **Analysis Tools** (Ideas 16-18): inspect, analyze, table
7. **Orchestrator** (Ideas 19-20): jn CLI and discovery service
8. **Extended Formats** (Ideas 24-26): YAML, TOML, Markdown
9. **Advanced Commands** (Ideas 27-30): join, merge, sh, vd

Total estimated work: 20-30 person-weeks for full migration.
