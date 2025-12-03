# Architecture Overview

> **Purpose**: How JN's components fit together at a high level.

---

## System Overview

JN is a collection of CLI tools that compose via Unix pipes:

```
┌─────────────────────────────────────────────────────────────────┐
│                         jn (orchestrator)                        │
│  Parses commands, resolves addresses, spawns tool pipelines     │
└─────────────────────────────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
    ┌─────────┐            ┌─────────┐            ┌─────────┐
    │ jn-cat  │            │jn-filter│            │ jn-put  │
    │ (read)  │────pipe────│(transform)───pipe────│ (write) │
    └─────────┘            └─────────┘            └─────────┘
         │                       │                       │
         ▼                       ▼                       ▼
    ┌─────────┐            ┌─────────┐            ┌─────────┐
    │ Plugins │            │   ZQ    │            │ Plugins │
    │csv,json,│            │ Engine  │            │csv,json,│
    │http,... │            │         │            │table,...│
    └─────────┘            └─────────┘            └─────────┘
```

---

## Component Responsibilities

### Orchestrator (`jn`)

The main `jn` command is a thin dispatcher:
- Parses subcommand (cat, put, filter, head, tail, etc.)
- Routes to appropriate tool
- Passes through arguments

It does minimal work itself—real processing happens in tools and plugins.

### CLI Tools

Each tool handles one type of operation:

| Tool | Purpose | Input | Output |
|------|---------|-------|--------|
| `jn-cat` | Read sources | Files, URLs, profiles | NDJSON |
| `jn-put` | Write destinations | NDJSON | Files in any format |
| `jn-filter` | Transform data | NDJSON | NDJSON |
| `jn-head` | First N records | NDJSON | NDJSON |
| `jn-tail` | Last N records | NDJSON | NDJSON |
| `jn-join` | Combine sources | NDJSON + source | NDJSON |
| `jn-merge` | Concatenate sources | Multiple sources | NDJSON |
| `jn-analyze` | Compute statistics | NDJSON | JSON |
| `jn-inspect` | Discover structure | Address | JSON |
| `jn-table` | Pretty print | NDJSON | Formatted text |

### Plugins

Plugins handle format-specific operations:

| Role | Examples | Responsibility |
|------|----------|----------------|
| **Format** | csv, json, yaml, xlsx | Convert between format and NDJSON |
| **Protocol** | http, gmail, mcp | Fetch data from remote sources |
| **Compression** | gz, bz2, xz | Decompress/compress byte streams |
| **Database** | duckdb, sqlite | Query and stream results |

### Shared Libraries

Common functionality extracted into libraries:

| Library | Purpose |
|---------|---------|
| `libjn-core` | Buffered I/O, JSON handling, error patterns |
| `libjn-cli` | Argument parsing, help generation |
| `libjn-plugin` | Plugin interface, metadata output |
| `libjn-address` | Address parsing (format, params, compression) |
| `libjn-profile` | Profile loading, env substitution, merging |
| `libjn-discovery` | Plugin scanning, pattern matching, caching |

---

## Data Flow

### Simple Pipeline

```bash
jn cat data.csv | jn filter '.revenue > 1000' | jn put output.json
```

Becomes:

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  file    │────▶│   csv    │────▶│    zq    │────▶│   json   │────▶ file
│ data.csv │     │ (read)   │     │ (filter) │     │ (write)  │     output
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                      │                │                │
                   NDJSON           NDJSON           NDJSON
```

### Multi-Stage Pipeline

For `jn cat https://example.com/data.csv.gz`:

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│   URL    │────▶│   http   │────▶│    gz    │────▶│   csv    │────▶ stdout
│          │     │ (fetch)  │     │(decomp)  │     │ (parse)  │     (NDJSON)
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                      │                │                │
                   bytes            bytes            NDJSON
```

Three processes run concurrently:
1. HTTP fetches bytes, writes to pipe
2. GZ reads pipe, decompresses, writes to pipe
3. CSV reads pipe, parses, writes NDJSON

OS pipes handle backpressure automatically.

---

## Key Abstractions

### Address

An address specifies a data source or destination:

```
protocol://path~format?params
│         │    │       │
│         │    │       └── Query parameters
│         │    └── Format override
│         └── Resource path
└── Protocol (http, file, duckdb, etc.)
```

Examples:
- `data.csv` - Local file, format inferred
- `https://api.com/data~json` - URL with format override
- `@myapi/users?limit=10` - Profile reference with params
- `data.csv.gz` - Compression auto-detected

### Plugin

A plugin is an executable that:
- Accepts `--mode={read,write,raw,profiles}`
- Reads from stdin, writes to stdout
- Outputs metadata via `--jn-meta`
- Declares patterns it handles

### Profile

A profile is a reusable configuration:
- Stored as JSON in profile directories
- Supports hierarchical inheritance
- Substitutes environment variables
- Provides defaults and validation

### Pipeline

A pipeline is a sequence of processes connected by pipes:
- Each stage runs independently
- Data flows through OS pipe buffers
- SIGPIPE propagates shutdown backward
- Memory usage is constant

---

## Resolution Flow

When `jn cat @myapi/users?limit=10` runs:

```
1. Parse address
   ├── Type: profile reference
   ├── Namespace: myapi
   ├── Name: users
   └── Params: {limit: 10}

2. Resolve profile
   ├── Search: ~/.local/jn/profiles/http/myapi/users.json
   ├── Load: _meta.json + users.json (merged)
   └── Substitute: ${API_TOKEN} → actual token

3. Determine plugin
   ├── Profile type: http
   └── Plugin: http (supports read mode)

4. Build pipeline
   ├── Stage 1: http --mode=read (with URL, headers)
   └── Stage 2: (none, output is already NDJSON)

5. Execute
   ├── Spawn http plugin
   ├── Stream output to stdout
   └── Wait for completion
```

---

## Concurrency Model

### Process-Based Parallelism

Each pipeline stage runs as a separate OS process:

```
┌────────┐   pipe   ┌────────┐   pipe   ┌────────┐
│ CPU 1  │─────────▶│ CPU 2  │─────────▶│ CPU 3  │
│ fetch  │  64KB    │ parse  │  64KB    │ filter │
└────────┘  buffer  └────────┘  buffer  └────────┘
```

Benefits:
- True parallelism (no GIL)
- Automatic backpressure (pipe buffers)
- Clean isolation (separate memory)
- Simple debugging (standard tools)

### No Async, No Threads

JN deliberately avoids:
- **async/await**: Adds complexity, no real benefit for pipelines
- **threading**: Python GIL prevents parallelism, shared memory causes bugs
- **multiprocessing pools**: Overkill for linear pipelines

Processes + pipes are simpler and more robust.

---

## Plugin Language Support

### Zig Plugins (Performance)

High-performance plugins for common formats:
- csv, json, jsonl (formats)
- gz (compression)
- http (protocol)
- zq (filter engine)

Characteristics:
- Fast startup (<5ms)
- Low memory (~1MB)
- Single binary
- Cross-platform

### Python Plugins (Extensibility)

Complex or ecosystem-dependent plugins:
- xlsx (requires openpyxl)
- gmail (requires Google APIs)
- mcp (Model Context Protocol)
- parquet (requires pyarrow)

Characteristics:
- Rich library ecosystem
- Easy to write and modify
- PEP 723 for dependencies
- UV for isolation

### Priority Order

When multiple plugins match:
1. User plugins (`~/.local/jn/plugins/`)
2. Project plugins (`.jn/plugins/`)
3. Bundled plugins (`$JN_HOME/plugins/`)

Within same location:
- Zig plugins preferred over Python
- Longer patterns preferred (more specific)

---

## Error Handling

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Usage error (bad arguments) |
| 3 | Plugin error (plugin failed) |
| 4 | I/O error (file not found, network) |
| 141 | SIGPIPE (downstream closed) |

### Error Propagation

Errors flow through stderr:
```
jn cat broken.csv 2>&1
# Error: CSV parsing failed at line 42: unterminated quote
```

Pipeline errors include stage information:
```
jn cat data.csv | jn filter '.bad.expr' | jn put out.json
# Error in filter stage: invalid ZQ expression '.bad.expr'
```

---

## See Also

- [01-vision.md](01-vision.md) - Why this architecture
- [04-project-layout.md](04-project-layout.md) - Where components live
- [05-plugin-system.md](05-plugin-system.md) - Plugin interface details
- [08-streaming-backpressure.md](08-streaming-backpressure.md) - Why pipes work
