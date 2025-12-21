# JN Index Design

> **Purpose**: Implementation design for fast NDJSON lookup indexes

This document provides the detailed implementation design for JN Indexes, which enable O(1) key lookups and graph traversals on NDJSON files without scanning.

---

## Table of Contents

1. [Overview](#overview)
2. [Index File Format](#index-file-format)
3. [CLI Commands](#cli-commands)
4. [Library Architecture](#library-architecture)
5. [Tool Integration](#tool-integration)
6. [Implementation Phases](#implementation-phases)
7. [Performance Targets](#performance-targets)

---

## Overview

### Problem Statement

JN's streaming model excels at transformation pipelines but struggles with:

| Operation | Current Cost | With Index |
|-----------|--------------|------------|
| Key lookup | O(n) scan | O(1) |
| Hash join (large right) | O(n) memory | O(1) per lookup |
| Graph traversal | O(n) per hop | O(degree) per hop |

### Solution

Introduce derived index files that:
- Store key → byte offset mappings
- Are memory-mappable for efficient access
- Remain disposable and rebuildable
- Emit NDJSON output like all JN tools

### Core Principles

1. **NDJSON remains canonical** - Index is derived, deletable
2. **Streaming output** - Even random-access queries emit NDJSON
3. **Disk-first** - Use mmap, not in-memory data structures
4. **Explicit staleness** - Detect when source has changed
5. **Minimal surface** - Small CLI, obvious behavior

---

## Index File Format

### File Naming Convention

```
source.jsonl       → source.jsonl.jnx       (lookup index)
source.jsonl       → source.jsonl.jnx.graph (graph index)
```

Index files live alongside their source file.

### Lookup Index Structure (`.jnx`)

The index is a single binary file with three sections:

```
┌────────────────────────────────────────────────────────────┐
│                        HEADER (64 bytes)                   │
├────────────────────────────────────────────────────────────┤
│                     KEY TABLE (variable)                   │
├────────────────────────────────────────────────────────────┤
│                    OFFSET TABLE (variable)                 │
└────────────────────────────────────────────────────────────┘
```

#### Header (64 bytes)

```
Offset  Size  Field
------  ----  -----
0       4     Magic: "JNX\x01" (4 bytes)
4       4     Version: 1 (u32 little-endian)
8       4     Flags: (u32)
              - bit 0: unique (1) vs multi (0)
              - bit 1: composite key (1) vs single (0)
12      4     Key count (u32)
16      8     Key table offset (u64)
24      8     Key table size (u64)
32      8     Offset table offset (u64)
40      8     Offset table size (u64)
48      8     Source file size at build time (u64)
56      8     Source file mtime at build time (u64)
```

#### Key Table

Sorted array of key entries for binary search:

```
┌──────────────────────────────────────────┐
│ Key Entry 0                              │
│   key_hash: u64                          │
│   key_offset: u32 (into string pool)     │
│   key_length: u16                        │
│   posting_offset: u32 (into offset table)│
│   posting_count: u16                     │
├──────────────────────────────────────────┤
│ Key Entry 1                              │
│   ...                                    │
├──────────────────────────────────────────┤
│ String Pool                              │
│   (deduplicated key strings)             │
└──────────────────────────────────────────┘
```

Entry size: 20 bytes per key

#### Offset Table

Array of file offsets (byte positions in source NDJSON):

```
┌────────────────────────────────┐
│ offset[0]: u64                 │
│ offset[1]: u64                 │
│ ...                            │
└────────────────────────────────┘
```

### Graph Index Structure (`.jnx.graph`)

For adjacency-based traversals:

```
┌────────────────────────────────────────────────────────────┐
│                        HEADER (64 bytes)                   │
├────────────────────────────────────────────────────────────┤
│                    NODE TABLE (variable)                   │
├────────────────────────────────────────────────────────────┤
│                    EDGE TABLE (variable)                   │
├────────────────────────────────────────────────────────────┤
│                   PREDICATE TABLE (variable)               │
└────────────────────────────────────────────────────────────┘
```

#### Graph Header

```
Offset  Size  Field
------  ----  -----
0       4     Magic: "JNXG" (4 bytes)
4       4     Version: 1 (u32)
8       4     Flags (u32)
              - bit 0: has reverse index
12      4     Node count (u32)
16      4     Edge count (u32)
20      4     Predicate count (u32)
24      8     Node table offset (u64)
32      8     Edge table offset (u64)
40      8     Predicate table offset (u64)
48      8     Source file size (u64)
56      8     Source file mtime (u64)
```

#### Node Table

```
┌──────────────────────────────────────────┐
│ Node Entry                               │
│   node_id_hash: u64                      │
│   node_id_offset: u32                    │
│   node_id_length: u16                    │
│   outgoing_edge_offset: u32              │
│   outgoing_edge_count: u16               │
│   incoming_edge_offset: u32 (optional)   │
│   incoming_edge_count: u16 (optional)    │
└──────────────────────────────────────────┘
```

#### Edge Table

```
┌──────────────────────────────────────────┐
│ Edge Entry                               │
│   predicate_id: u16                      │
│   target_node_index: u32                 │
│   source_offset: u64 (in edges.jsonl)    │
└──────────────────────────────────────────┘
```

---

## CLI Commands

### `jn index build`

Build an index for a NDJSON file.

```bash
# Lookup index (single key)
jn index build customers.jsonl --on customer_id

# Lookup index (composite key)
jn index build transactions.jsonl --on "bank_code,account_number"

# Unique mode (one record per key, error on duplicates)
jn index build customers.jsonl --on customer_id --mode unique

# Multi mode (default, multiple records per key)
jn index build orders.jsonl --on customer_id --mode multi

# Graph index
jn index build edges.jsonl --graph --from from --pred pred --to to

# Graph with reverse index (enables in() queries)
jn index build edges.jsonl --graph --from from --pred pred --to to --reverse
```

**Output (stderr, JSONL events):**

```json
{"event":"build_start","source":"customers.jsonl","key":"customer_id"}
{"event":"progress","records":10000,"keys":8500}
{"event":"build_complete","records":50000,"keys":42000,"size_bytes":1048576,"duration_ms":234}
```

**Exit codes:**
- 0: Success
- 1: Build failed (I/O error, invalid JSON)
- 2: Usage error

### `jn index get`

Lookup records by key.

```bash
# Single key lookup
jn index get customers.jsonl --key customer_id --eq C123

# Multiple values (OR)
jn index get customers.jsonl --key customer_id --eq C123,C456,C789

# Read keys from stdin
echo -e "C123\nC456" | jn index get customers.jsonl --key customer_id --stdin
```

**Output (stdout):** Matching records as NDJSON

```json
{"customer_id":"C123","name":"Alice","region":"West"}
```

**Fallback behavior:** If index doesn't exist or is stale, falls back to scan with warning:

```json
{"event":"index_fallback","reason":"stale","source":"customers.jsonl"}
```

### `jn index check`

Validate index integrity and freshness.

```bash
jn index check customers.jsonl
```

**Output:**

```json
{"valid":true,"fresh":true,"records":50000,"keys":42000,"size_bytes":1048576}
```

Or if stale:

```json
{"valid":true,"fresh":false,"reason":"source_modified","source_mtime":1703100000,"index_mtime":1703000000}
```

### `jn index stats`

Show index statistics.

```bash
jn index stats customers.jsonl
```

**Output:**

```json
{
  "source": "customers.jsonl",
  "index": "customers.jsonl.jnx",
  "type": "lookup",
  "mode": "multi",
  "key": "customer_id",
  "records": 50000,
  "unique_keys": 42000,
  "avg_records_per_key": 1.19,
  "index_size_bytes": 1048576,
  "source_size_bytes": 52428800,
  "compression_ratio": 0.02,
  "build_time": "2024-12-21T10:30:00Z"
}
```

### `jn index update`

Incremental update for append-only files.

```bash
jn index update customers.jsonl
```

**Behavior:**
1. Check if source has only appended data (size increased, mtime changed)
2. If yes, index only new records and merge
3. If source was modified in-place, emit warning and require `--full`

```json
{"event":"update_mode","mode":"incremental","new_records":1000}
```

Or:

```json
{"event":"update_mode","mode":"full_required","reason":"source_modified"}
```

---

## Library Architecture

### New Library: `jn-index`

Location: `libs/zig/jn-index/`

```
jn-index/
├── build.zig
├── build.zig.zon
└── src/
    ├── root.zig           # Public API
    ├── lookup.zig         # Lookup index implementation
    ├── graph.zig          # Graph index implementation
    ├── format.zig         # Binary format read/write
    ├── mmap.zig           # Memory mapping utilities
    └── hash.zig           # Key hashing (xxhash)
```

### Public API

```zig
// jn-index/src/root.zig

/// Build a lookup index
pub fn buildLookupIndex(
    allocator: Allocator,
    source_path: []const u8,
    key_field: []const u8,
    options: BuildOptions,
) !void;

/// Build a graph index
pub fn buildGraphIndex(
    allocator: Allocator,
    source_path: []const u8,
    from_field: []const u8,
    pred_field: []const u8,
    to_field: []const u8,
    options: GraphBuildOptions,
) !void;

/// Open a lookup index for queries
pub fn openLookupIndex(path: []const u8) !LookupIndex;

/// Query a lookup index
pub const LookupIndex = struct {
    /// Lookup records by key, returns iterator over byte offsets
    pub fn lookup(self: *LookupIndex, key: []const u8) !OffsetIterator;

    /// Check if index is fresh relative to source
    pub fn isFresh(self: *LookupIndex) bool;

    /// Close and unmap
    pub fn close(self: *LookupIndex) void;
};

/// Open a graph index
pub fn openGraphIndex(path: []const u8) !GraphIndex;

pub const GraphIndex = struct {
    /// Get outgoing edges from a node
    pub fn out(self: *GraphIndex, node_id: []const u8) !EdgeIterator;

    /// Get incoming edges to a node (requires --reverse at build)
    pub fn in(self: *GraphIndex, node_id: []const u8) !EdgeIterator;

    /// Multi-hop expansion
    pub fn expand(
        self: *GraphIndex,
        seed: []const u8,
        max_hops: u32,
        pred_filter: ?[]const u8,
    ) !NodeIterator;
};
```

### Memory Mapping Strategy

```zig
// mmap.zig

pub fn mapFile(path: []const u8) !MappedFile {
    const fd = try std.os.open(path, .{ .ACCMODE = .RDONLY }, 0);
    const stat = try std.os.fstat(fd);
    const ptr = try std.os.mmap(
        null,
        stat.size,
        std.os.PROT.READ,
        std.os.MAP.PRIVATE,
        fd,
        0,
    );
    return MappedFile{
        .data = ptr,
        .size = stat.size,
        .fd = fd,
    };
}
```

---

## Tool Integration

### `jn-join` Enhancement

Add `--right-index` flag to use index for right-side lookups instead of hash table:

```bash
# Current: loads customers.jsonl into memory hash table
jn cat orders.jsonl | jn join customers.jsonl --on customer_id

# New: uses index, constant memory
jn cat orders.jsonl | jn join customers.jsonl --on customer_id --right-index
```

Implementation changes to `tools/zig/jn-join/main.zig`:

```zig
const JoinConfig = struct {
    // ... existing fields ...
    use_right_index: bool = false,
};

fn runJoin(allocator: Allocator, config: JoinConfig, right_source: []const u8) !void {
    if (config.use_right_index) {
        // Use indexed join
        const index = try jn_index.openLookupIndex(indexPath(right_source));
        defer index.close();

        // For each left record, lookup in index
        // Seek to offset in source file to read matched records
        try runIndexedJoin(allocator, config, right_source, index);
    } else {
        // Current hash table join
        try runHashJoin(allocator, config, right_source);
    }
}
```

### New Tool: `jn-graph`

Location: `tools/zig/jn-graph/`

```bash
# Expand from seed node
jn graph expand --edges edges.jsonl --seed "C123" --hops 3

# Filter by predicate
jn graph expand --edges edges.jsonl --seed "C123" --pred subClassOf --hops 3

# Include edge records in output
jn graph expand --edges edges.jsonl --seed "C123" --hops 2 --emit-edges

# Read seeds from stdin
jn cat seeds.jsonl | jn graph expand --edges edges.jsonl --seed-field id --hops 2
```

**Output modes:**

Nodes only (default):
```json
{"id":"C123","level":0}
{"id":"C456","level":1,"via":"subClassOf"}
{"id":"C789","level":2,"via":"subClassOf"}
```

With edges (`--emit-edges`):
```json
{"type":"node","id":"C123","level":0}
{"type":"edge","from":"C123","pred":"subClassOf","to":"C456"}
{"type":"node","id":"C456","level":1}
```

### Orchestrator Integration

The `jn` orchestrator routes index commands:

```bash
jn index build ...   →  jn-index build ...
jn index get ...     →  jn-index get ...
jn graph expand ...  →  jn-graph expand ...
```

Add to `tools/zig/jn/main.zig`:

```zig
const subcommands = .{
    // ... existing ...
    .{ "index", "jn-index" },
    .{ "graph", "jn-graph" },
};
```

---

## Implementation Phases

### Phase 1: Core Index Library (Week 1)

**Goal:** Build and query lookup indexes

- [ ] Create `libs/zig/jn-index/` library structure
- [ ] Implement binary format read/write (`format.zig`)
- [ ] Implement mmap utilities (`mmap.zig`)
- [ ] Implement lookup index build (`lookup.zig`)
- [ ] Implement lookup index query
- [ ] Add staleness detection (file size + mtime check)
- [ ] Unit tests for library

**Deliverable:** Working `jn_index.buildLookupIndex()` and `jn_index.openLookupIndex()`

### Phase 2: CLI Tool (Week 2)

**Goal:** User-facing index commands

- [ ] Create `tools/zig/jn-index/` tool
- [ ] Implement `build` subcommand
- [ ] Implement `get` subcommand
- [ ] Implement `check` subcommand
- [ ] Implement `stats` subcommand
- [ ] Add to orchestrator routing
- [ ] Integration tests

**Deliverable:** Working `jn index build`, `jn index get`

### Phase 3: Join Integration (Week 3)

**Goal:** Index-backed joins

- [ ] Add `--right-index` flag to `jn-join`
- [ ] Implement indexed join path
- [ ] Handle fallback to hash join
- [ ] Emit JSONL events for query plan
- [ ] Add `--explain` flag
- [ ] Benchmark vs hash join

**Deliverable:** `jn join --right-index` working

### Phase 4: Graph Index (Week 4)

**Goal:** Graph traversal support

- [ ] Implement graph index format (`graph.zig`)
- [ ] Implement graph index build
- [ ] Create `tools/zig/jn-graph/` tool
- [ ] Implement `expand` command
- [ ] Support `--reverse` for in() queries
- [ ] Integration tests

**Deliverable:** Working `jn graph expand`

### Phase 5: Incremental Updates (Week 5)

**Goal:** Efficient append-only updates

- [ ] Detect append-only changes
- [ ] Implement delta segment format
- [ ] Implement segment merge at query time
- [ ] Implement `compact` command
- [ ] Handle non-append modifications

**Deliverable:** Working `jn index update`

### Phase 6: Polish & Documentation

- [ ] Add `spec/16-indexes.md` to spec docs
- [ ] Update `CLAUDE.md` with new commands
- [ ] Performance benchmarks
- [ ] Error message review
- [ ] Edge case testing

---

## Performance Targets

### Lookup Index

| Metric | Target | Notes |
|--------|--------|-------|
| Build speed | >100k records/sec | Single-threaded |
| Index size | <5% of source | Typical compression |
| Lookup latency | <10ms cold | First query |
| Lookup latency | <1ms warm | Cached in page cache |
| Memory usage | <10MB | Regardless of index size |

### Graph Index

| Metric | Target | Notes |
|--------|--------|-------|
| Build speed | >50k edges/sec | Single-threaded |
| out() latency | <1ms | Per node |
| 3-hop expand | <100ms | 1000 result nodes |
| Memory usage | <10MB | Regardless of graph size |

### Indexed Join

| Metric | Target | Notes |
|--------|--------|-------|
| Throughput | >50k joins/sec | With index |
| Memory | O(1) | Not O(right-side) |
| Latency overhead | <10% | vs hash join for small right |

---

## Design Decisions

### Why Binary Format, Not SQLite?

| Factor | Binary | SQLite |
|--------|--------|--------|
| Dependency | None | Adds ~1MB |
| mmap efficiency | Perfect | Has overhead |
| Build complexity | Low | Higher |
| Query flexibility | Low | High |
| Feature scope | Just lookups | Too much |

JN Indexes are intentionally minimal. SQLite would be overkill and violate the "accelerator, not database" principle.

### Why xxHash for Keys?

- Extremely fast (>10 GB/s)
- 64-bit output (low collision probability)
- No cryptographic overhead
- Well-suited for hash tables and binary search

### Why Sorted Keys with Binary Search?

- Predictable O(log n) lookup
- Cache-friendly access pattern
- Simple implementation
- Works well with mmap

Alternative considered: Hash table. Rejected because:
- Less predictable memory access
- Harder to mmap efficiently
- Binary search is fast enough for <10M keys

### Why File Offsets, Not Record Copies?

Storing offsets instead of copying records:
- **Smaller indexes**: 8 bytes vs average record size
- **Always fresh data**: Reads from source, not copy
- **Simpler updates**: Just append new offsets

Trade-off: Requires seek to source file. Acceptable because:
- SSD seeks are fast (<0.1ms)
- OS page cache helps
- NDJSON lines are typically <1KB

---

## Error Handling

### Staleness Detection

```
Source modified? = (current_size != index_size) OR (current_mtime > index_mtime)
```

When stale:
1. Emit warning to stderr: `{"event":"index_stale","source":"file.jsonl"}`
2. Fall back to scan (default) or error (with `--strict`)

### Corrupt Index

If index fails validation:
1. Emit error: `{"event":"index_corrupt","source":"file.jsonl"}`
2. Delete corrupt index
3. Rebuild if `--auto-rebuild`, else error

### Build Failures

| Failure | Behavior |
|---------|----------|
| Invalid JSON line | Skip line, count skipped |
| Missing key field | Skip line, count skipped |
| Disk full | Error, delete partial index |
| Source disappears mid-build | Error, delete partial index |

Report at end:
```json
{"event":"build_complete","records":50000,"skipped":12,"keys":42000}
```

---

## Future Considerations

### Not in Scope (v1)

- **Full-text search**: Use dedicated tools (tantivy, sqlite fts)
- **Range queries**: Would require different index structure
- **Distributed indexes**: Out of scope
- **Real-time updates**: JN is batch-oriented
- **Transactions**: Not a database

### Possible Future Extensions

- **Bloom filters**: For negative lookups
- **Prefix indexes**: For LIKE queries
- **Parallel build**: Multi-threaded index construction
- **Compressed indexes**: For very large key sets

---

## File Inventory

New files to create:

```
libs/zig/jn-index/
├── build.zig
├── build.zig.zon
└── src/
    ├── root.zig
    ├── lookup.zig
    ├── graph.zig
    ├── format.zig
    ├── mmap.zig
    └── hash.zig

tools/zig/jn-index/
├── build.zig
├── build.zig.zon
└── main.zig

tools/zig/jn-graph/
├── build.zig
├── build.zig.zon
└── main.zig
```

Files to modify:

```
tools/zig/jn/main.zig          # Add index, graph routing
tools/zig/jn-join/main.zig     # Add --right-index
Makefile                        # Add new targets
CLAUDE.md                       # Document new commands
```

---

## Summary

JN Indexes provide fast key lookups and graph traversals while preserving JN's core properties:

- **NDJSON canonical**: Indexes are derived, disposable
- **Streaming output**: Queries emit NDJSON line-by-line
- **Predictable resources**: mmap keeps memory bounded
- **Composable**: Integrates with existing pipeline tools
- **Minimal surface**: Few commands, obvious behavior

The implementation adds one library (`jn-index`) and two tools (`jn-index`, `jn-graph`) following established patterns in the codebase.
