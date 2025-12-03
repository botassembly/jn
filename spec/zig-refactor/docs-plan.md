# JN Documentation Suite: Design Plan

> **Goal**: Replace the current four zig-refactor documents with 10 focused, high-value architecture and design documents that explain **what** JN is and **why** it works the way it does.

## Current State

The existing four documents are:
- `plan.md` - Implementation plan with detailed checkboxes (1050+ lines)
- `brainstorm.md` - 30 ideas with dependencies (770+ lines)
- `plugin-profiles.md` - Profile-as-plugin-capability proposal (470+ lines)
- `plugin-matching.md` - Pattern matching and format resolution (485+ lines)

**Problems with current docs:**
- Mix architecture concepts with implementation details
- Code-heavy (Zig snippets scattered throughout)
- Implementation checkboxes create maintenance burden
- Overlap and redundancy between documents
- Missing user-facing documentation

## Proposed Documentation Suite

### Document Structure

Each document follows a consistent structure:
1. **Purpose** - One-sentence summary of what this document covers
2. **Why This Matters** - Business/technical motivation
3. **Core Concepts** - The "what" explained simply
4. **How It Works** - Conceptual explanation (not code)
5. **Design Decisions** - Key choices and trade-offs
6. **See Also** - Links to related documents

---

## The 10 Documents

### 01. Vision and Philosophy
**`01-vision.md`**

**Purpose**: Why JN exists and what makes it different from other ETL tools.

**Contents**:
- The problem: AI agents need to create data tools on-demand
- Why existing ETL tools don't work (Pandas, Spark, dbt)
- JN's unique value proposition: Agent-native ETL
- Core philosophy: Unix processes, NDJSON, streaming
- Non-goals: What JN deliberately doesn't do
- Success criteria: How we measure JN's effectiveness

**Why separate**: This is the "north star" document that everything else derives from. New contributors should read this first.

---

### 02. Architecture Overview
**`02-architecture.md`**

**Purpose**: How JN's components fit together at a high level.

**Contents**:
- System diagram: CLI → Orchestrator → Plugins → Pipes
- Component responsibilities:
  - `jn` command (thin orchestrator)
  - CLI tools (cat, put, filter, head, tail, etc.)
  - Plugins (formats, protocols, compression)
  - Libraries (core streaming, CLI parsing, plugin interface)
- Data flow: Source → (Protocol) → (Decompress) → Format → NDJSON
- Key abstractions: Address, Plugin, Profile, Pipeline
- Current vs target state (Python → Zig migration)

**Why separate**: Provides the mental model for understanding everything else. The "30,000 foot view" that other docs drill into.

---

### 03. Users Guide
**`03-users-guide.md`**

**Purpose**: How to use JN effectively for common tasks.

**Contents**:
- Installation and setup
- Quick start: Your first pipeline
- Core commands reference:
  - `jn cat` - Read any source
  - `jn put` - Write any format
  - `jn filter` - Transform data
  - `jn head/tail` - Truncate streams
  - `jn inspect` - Discover and analyze
  - `jn profile` - Manage profiles
- Address syntax: `source[~format][?params]`
- Common workflows:
  - CSV → JSON conversion
  - API data extraction
  - Multi-source merging
  - Data exploration
- Troubleshooting guide

**Why separate**: User-facing documentation should be separate from internal architecture. This is what users read first.

---

### 04. Project Layout
**`04-project-layout.md`**

**Purpose**: Where everything lives and why it's organized that way.

**Contents**:
- Repository structure:
  ```
  jn/
  ├── src/jn/        # Python CLI (current, being migrated)
  ├── libs/zig/      # Shared Zig libraries
  ├── tools/zig/     # Zig CLI tools
  ├── plugins/       # Format/protocol plugins
  │   ├── zig/       # High-performance Zig plugins
  │   └── python/    # User-extensible Python plugins
  ├── jn_home/       # Bundled defaults (plugins, profiles)
  └── spec/          # Documentation
  ```
- Plugin directory hierarchy:
  - Project (`.jn/plugins/`)
  - User (`~/.local/jn/plugins/`)
  - Bundled (`$JN_HOME/plugins/`)
- Profile directory hierarchy
- Why this structure? Design rationale
- Where to add new things

**Why separate**: Onboarding documentation. Contributors need to know where things go before they can contribute.

---

### 05. Plugin System
**`05-plugin-system.md`**

**Purpose**: How plugins work and what they can do.

**Contents**:
- What is a plugin? Standalone executable with standard interface
- Plugin roles:
  - **Format** - Bidirectional data conversion (CSV, JSON, YAML)
  - **Protocol** - Remote data access (HTTP, Gmail, MCP)
  - **Compression** - Byte-level transformation (gzip, bzip2)
  - **Database** - Query interfaces (DuckDB, SQLite)
- Plugin modes:
  - `read` - Source → NDJSON
  - `write` - NDJSON → Destination
  - `raw` - Byte passthrough
  - `profiles` - List/describe available configurations
- Plugin metadata: PEP 723 (Python) vs `--jn-meta` (Zig)
- Plugin discovery: How JN finds and caches plugins
- Language support: Zig (high-performance), Python (extensibility)

**Why separate**: The plugin system is the core abstraction. Understanding plugins is prerequisite to understanding matching, profiles, and pipelines.

---

### 06. Matching and Resolution
**`06-matching-resolution.md`**

**Purpose**: How JN decides which plugin handles a given address.

**Contents**:
- The resolution problem: `data.csv.gz` → which plugin(s)?
- Address parsing:
  - Protocol detection (`http://`, `duckdb://`)
  - Format override (`~csv`, `~json`)
  - Parameters (`?delimiter=;`)
  - Compression (`.gz`, `.bz2`)
  - Profile references (`@namespace/name`)
- Pattern matching:
  - Regex patterns in plugin metadata
  - Specificity scoring (longer patterns win)
  - Priority ordering (user > bundled, Zig > Python)
- Multi-stage resolution:
  - Protocol stage (fetch bytes)
  - Compression stage (decompress)
  - Format stage (parse to NDJSON)
- Format override: How `~format` bypasses pattern matching
- CSV delimiter detection: Auto-detection algorithm

**Why separate**: Resolution is complex enough to warrant its own document. It's the "brain" of JN's routing logic.

---

### 07. Profile System
**`07-profiles.md`**

**Purpose**: How profiles configure and simplify data access.

**Contents**:
- What is a profile? Reusable configuration for data sources
- Profile types:
  - **HTTP** - API endpoints with auth and headers
  - **ZQ** - Saved filter expressions with parameters
  - **Database** - Connection strings and default queries
- Profile hierarchy:
  - `_meta.json` - Base configuration (auth, base_url)
  - `endpoint.json` - Specific endpoints
  - Deep merge semantics
- Profile sources (priority order):
  1. Project filesystem (`.jn/profiles/`)
  2. User filesystem (`~/.local/jn/profiles/`)
  3. Plugin-bundled profiles
  4. Plugin-discovered profiles (dynamic)
- Environment variable substitution: `${VAR}` syntax
- Profile reference syntax: `@namespace/name?params`
- Profiles as plugin capability: `--mode=profiles`
- Dynamic profile discovery: DuckDB tables, API introspection

**Why separate**: Profiles are a key differentiator for JN. They deserve deep treatment.

---

### 08. Streaming and Backpressure
**`08-streaming-backpressure.md`**

**Purpose**: Why JN uses processes and pipes, and how this enables constant-memory streaming.

**Contents**:
- The memory problem: Why buffering fails at scale
- The solution: OS pipes with automatic backpressure
- How pipe buffers work:
  - 64KB kernel buffer
  - Blocking writes when full
  - Blocking reads when empty
- SIGPIPE and early termination:
  - Why `head -n 10` stops upstream
  - The critical `stdout.close()` pattern
  - Signal propagation through pipeline
- Performance characteristics:
  - Memory: O(pipe_buffer) not O(data_size)
  - Parallelism: Multi-CPU via processes
  - Latency: First output immediately, not after full processing
- Why not async? Comparison with asyncio approach
- Why not threads? GIL and shared memory problems
- Testing backpressure: How to verify it works
- When streaming doesn't work: Format constraints (XLSX, etc.)

**Why separate**: This is the most important technical concept in JN. Performance depends on understanding this. Consolidates and improves on existing `arch-backpressure.md`.

---

### 09. Joining and Multi-Source Operations
**`09-joining-operations.md`**

**Purpose**: How to combine data from multiple sources.

**Contents**:
- The join problem: Correlating data across sources
- `jn-join` command:
  - Hash join architecture (right buffered, left streamed)
  - Join key modes: natural, named, composite
  - Join types: inner, left, (outer considerations)
  - Range/condition joins: `.line >= .start_line`
  - Output modes: embed as array, flatten, pick fields
  - Aggregation functions: count, sum, avg, min, max
- `jn-merge` command:
  - Sequential source combination
  - Source tagging (`_source`, `_label` fields)
  - Error handling: fail-safe vs fail-fast
- Memory considerations:
  - Right source must fit in memory
  - Large join strategies
- Use cases:
  - Enriching records from lookup table
  - Combining API data with local files
  - Multi-source data consolidation

**Why separate**: Joins are complex operations with their own design space. Users need dedicated documentation.

---

### 10. Migration Roadmap
**`10-migration-roadmap.md`**

**Purpose**: The plan for migrating from Python to Zig.

**Contents**:
- Current state: Python CLI with mixed Zig plugins
- Target state: Zig core with Python extensibility
- What's migrating:
  - CLI tools (cat, put, filter, head, tail, etc.)
  - Core libraries (streaming, CLI parsing, plugin interface)
  - Format plugins (CSV, JSON, JSONL, GZ)
  - Protocol plugins (HTTP)
- What stays in Python:
  - Complex formats (XLSX, Parquet)
  - OAuth-based protocols (Gmail)
  - User-extensible plugins
- Migration phases:
  1. Foundation libraries
  2. Plugin refactor
  3. Address parsing
  4. Profile system
  5. Core CLI tools
  6. HTTP protocol
  7. Analysis tools
  8. Plugin discovery
  9. Orchestrator
  10. Extended formats
- Success metrics:
  - Startup time: 50-100ms → <5ms
  - Memory: O(data) → O(1)
  - Lines of code: ~10K → ~5K
  - Binary size: ~5MB total
- Risk mitigation strategies

**Why separate**: The migration plan is important but should be separate from architecture docs. It's time-bound; architecture docs should be timeless.

---

## Document Dependencies

```
01-vision
    ↓
02-architecture ←──────────────────────┐
    ↓                                  │
03-users-guide                         │
    ↓                                  │
04-project-layout                      │
    ↓                                  │
05-plugin-system ──→ 06-matching-resolution
    ↓                     ↓
07-profiles ←─────────────┘
    ↓
08-streaming-backpressure
    ↓
09-joining-operations
    ↓
10-migration-roadmap ──────────────────┘
```

**Reading order for**:
- New users: 03 → 01 → 02
- New contributors: 01 → 02 → 04 → 05
- Performance understanding: 08 (standalone)
- Migration work: 10 → 02 → 05

---

## Content Migration from Current Docs

| Current Document | Migrates To |
|------------------|-------------|
| `brainstorm.md` §Executive Summary | `01-vision.md` |
| `brainstorm.md` §Dependency Graph | `02-architecture.md` |
| `brainstorm.md` §Ideas 1-8 (foundation) | `05-plugin-system.md` |
| `brainstorm.md` §Ideas 14-15 (profiles, addresses) | `06-matching-resolution.md`, `07-profiles.md` |
| `brainstorm.md` §Ideas 27-28 (join, merge) | `09-joining-operations.md` |
| `brainstorm.md` §Part 5 (Python plugins) | `05-plugin-system.md` §Language Support |
| `plan.md` §Architecture Overview | `02-architecture.md` |
| `plan.md` §Features NOT Being Migrated | `10-migration-roadmap.md` |
| `plan.md` §Phase 1-13 | `10-migration-roadmap.md` |
| `plugin-profiles.md` (entire) | `07-profiles.md` |
| `plugin-matching.md` §Pattern Matching | `06-matching-resolution.md` |
| `plugin-matching.md` §CSV Variations | `06-matching-resolution.md` §CSV delimiter detection |
| `arch-backpressure.md` (existing done/) | `08-streaming-backpressure.md` (expanded) |

---

## What Gets Removed

The following content is intentionally NOT migrated:

1. **Implementation checkboxes** - These belong in issue tracking, not docs
2. **Code snippets** - Conceptual docs shouldn't have code; link to source instead
3. **Line count estimates** - Too granular for architecture docs
4. **Zig struct definitions** - Implementation detail, not architecture
5. **Timeline estimates** - Dates in docs go stale immediately

---

## Naming Convention

Documents use numbered prefixes for suggested reading order:
- `01-` through `03-`: Start here (vision, architecture, usage)
- `04-` through `07-`: Core concepts (layout, plugins, matching, profiles)
- `08-` through `09-`: Deep dives (streaming, joins)
- `10-`: Planning (migration roadmap)

---

## Success Criteria

The new documentation suite succeeds if:

1. **New users** can understand what JN does and how to use it in <10 minutes
2. **New contributors** can understand the architecture in <30 minutes
3. **No document exceeds 500 lines** (focused, readable)
4. **Documents can be read independently** (minimal prerequisites)
5. **Architecture docs remain valid** even as implementation changes
6. **No maintenance burden** from checkboxes, code snippets, or dates

---

## Next Steps

1. [ ] Review and approve this plan
2. [ ] Create `01-vision.md` (sets the tone for all other docs)
3. [ ] Create `08-streaming-backpressure.md` (key technical concept)
4. [ ] Create `03-users-guide.md` (user-facing priority)
5. [ ] Create remaining docs in dependency order
6. [ ] Archive current four documents to `spec/zig-refactor/archive/`
7. [ ] Update `spec/README.md` with new document structure
