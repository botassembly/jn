# JN Index Design

> **Purpose**: Implementation design for fast NDJSON lookup indexes

This document provides the detailed implementation design for JN Indexes, which enable O(1) key lookups and graph traversals on NDJSON files without scanning.

---

## Table of Contents

1. [Overview](#overview)
2. [Index File Naming](#index-file-naming)
3. [Lookup Index Format](#lookup-index-format)
4. [Graph Traversal Strategy](#graph-traversal-strategy)
5. [Key Encoding](#key-encoding)
6. [Staleness Detection](#staleness-detection)
7. [CLI Commands](#cli-commands)
8. [Library Architecture](#library-architecture)
9. [Tool Integration](#tool-integration)
10. [Build Algorithm](#build-algorithm)
11. [Incremental Updates](#incremental-updates)
12. [Error Handling](#error-handling)
13. [Implementation Phases](#implementation-phases)
14. [Performance Targets](#performance-targets)

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
6. **Predictable resources** - Query memory bounded; build memory documented

---

## Index File Naming

### Convention: Key-Specific Index Files

A single source file can have multiple indexes (on different keys). Each index is named by its key specification:

```
# Single key
customers.jsonl.jnx.customer_id

# Composite key (fields joined with +)
transactions.jsonl.jnx.bank_code+account_number

# Graph adjacency (from → to via predicate)
edges.jsonl.jnx.from                    # outgoing edges
edges.jsonl.jnx.to                      # incoming edges (reverse)
```

### CLI Mapping

| Command | Index File Used |
|---------|-----------------|
| `jn index build customers.jsonl --on customer_id` | `customers.jsonl.jnx.customer_id` |
| `jn index build txns.jsonl --on "bank,acct"` | `txns.jsonl.jnx.bank+acct` |
| `jn index get customers.jsonl --key customer_id --eq C123` | `customers.jsonl.jnx.customer_id` |

### Explicit Output Path

Override with `--out`:

```bash
jn index build customers.jsonl --on customer_id --out /tmp/cust.idx
```

---

## Lookup Index Format

### File Structure

The index is a single binary file with five sections:

```
┌────────────────────────────────────────────────────────────┐
│                        HEADER (128 bytes)                  │
├────────────────────────────────────────────────────────────┤
│                     KEY TABLE (variable)                   │
├────────────────────────────────────────────────────────────┤
│                   STRING POOL (variable)                   │
├────────────────────────────────────────────────────────────┤
│                   OFFSET TABLE (variable)                  │
├────────────────────────────────────────────────────────────┤
│                   CHECKSUM (16 bytes)                      │
└────────────────────────────────────────────────────────────┘
```

### Header (128 bytes, offset 0)

All integers are little-endian.

```
Offset  Size  Field                  Description
------  ----  -----                  -----------
0       4     magic                  "JNX\x02" (version 2)
4       4     version                2 (u32)
8       4     flags                  (u32) bit 0: unique(1)/multi(0)
                                           bit 1: composite key
12      4     key_count              Number of unique keys (u32)
16      4     posting_count          Total postings (u32)
20      4     key_field_count        Number of fields in key (u32, 1 for simple)
24      8     key_table_offset       Absolute byte offset (u64)
32      8     key_table_size         Size in bytes (u64)
40      8     string_pool_offset     Absolute byte offset (u64)
48      8     string_pool_size       Size in bytes (u64)
56      8     offset_table_offset    Absolute byte offset (u64)
64      8     offset_table_size      Size in bytes (u64)
72      8     source_size            Source file size at build (u64)
80      8     source_mtime_ns        Source mtime in nanoseconds (u64)
88      8     source_inode           Source inode/file-id (u64)
96      8     source_dev             Source device id (u64)
104     8     build_timestamp_ns     When index was built (u64)
112     16    reserved               Zero-filled for future use
```

### Key Table

Location: `[key_table_offset, key_table_offset + key_table_size)`

Sorted array of key entries. **Sort order**:
1. Primary: `key_hash` ascending
2. Secondary: key bytes lexicographic ascending
3. Tertiary: key length ascending (for prefix matches)

Each entry is **24 bytes**:

```
Offset  Size  Field              Description
------  ----  -----              -----------
0       8     key_hash           xxh3_64 hash of key bytes (u64)
8       4     string_offset      Offset into string pool (u32, relative to string_pool_offset)
12      4     string_length      Key string length in bytes (u32)
16      4     posting_offset     Index into offset table (u32, entry index not byte offset)
20      4     posting_count      Number of postings for this key (u32)
```

Entry size: 24 bytes × key_count

### String Pool

Location: `[string_pool_offset, string_pool_offset + string_pool_size)`

Concatenated key strings (UTF-8 bytes). No delimiters; lengths come from key table entries.

```
┌────────────────────────────────────────────────────────────┐
│ "C001" "C002" "C003" ... (packed, no separators)          │
└────────────────────────────────────────────────────────────┘
```

To read key string for entry `i`:
```
key_bytes = mmap[string_pool_offset + entry.string_offset : +entry.string_length]
```

### Offset Table

Location: `[offset_table_offset, offset_table_offset + offset_table_size)`

Array of source file byte offsets (u64 each):

```
┌────────────────────────────────────────────────────────────┐
│ offset[0]: u64  (byte position of first record)           │
│ offset[1]: u64                                            │
│ ...                                                        │
│ offset[posting_count-1]: u64                              │
└────────────────────────────────────────────────────────────┘
```

Size: 8 bytes × posting_count

To get postings for key entry `i`:
```
postings = offset_table[entry.posting_offset : +entry.posting_count]
```

### Checksum Section (16 bytes)

Location: last 16 bytes of file

```
Offset  Size  Field              Description
------  ----  -----              -----------
0       4     key_table_crc32    CRC32 of key table bytes
4       4     string_pool_crc32  CRC32 of string pool bytes
8       4     offset_table_crc32 CRC32 of offset table bytes
12      4     header_crc32       CRC32 of header bytes (0-127)
```

CRC32 uses IEEE polynomial (same as zlib).

---

## Graph Traversal Strategy

### V1: Reuse Lookup Indexes

Rather than introduce a separate `.jnxg` format, v1 implements graph traversal using lookup indexes on edge files:

```bash
# Build indexes on the edge file
jn index build edges.jsonl --on from    # outgoing edges
jn index build edges.jsonl --on to      # incoming edges (for reverse traversal)
```

Then `jn graph expand` uses these indexes:

```bash
# Expand outgoing from seed
jn graph expand edges.jsonl --seed "C123" --hops 3

# Implementation: repeatedly calls index lookups on "from" field
```

### Why This Approach

| Factor | Separate Graph Format | Reuse Lookup Index |
|--------|----------------------|-------------------|
| Implementation complexity | High | Low |
| Code reuse | Minimal | Maximum |
| Memory model | New | Proven |
| Incremental updates | Complex | Straightforward |
| Flexibility | Specialized | General |

Graph-specific optimizations (predicate dictionaries, projected adjacency) can be added in v2 after validating the core index machinery.

### Graph Operations via Lookup

| Operation | Implementation |
|-----------|---------------|
| `out(node)` | `index get edges.jsonl --key from --eq node` |
| `in(node)` | `index get edges.jsonl --key to --eq node` |
| `expand(seed, hops)` | BFS using `out()` repeatedly |
| `expand --reverse` | BFS using `in()` repeatedly |

---

## Key Encoding

### Hash Function

- **Algorithm**: xxh3_64 (XXHash3, 64-bit variant)
- **Seed**: 0 (constant, not configurable)
- **Input**: Raw UTF-8 bytes of canonical key string

### Single Key Encoding

Extract the JSON value for the key field and convert to canonical string:

| JSON Type | Canonical String |
|-----------|-----------------|
| string | Exact UTF-8 bytes (no quotes) |
| number | Decimal with minimal representation (no trailing zeros, no leading zeros except "0.x") |
| boolean | `"true"` or `"false"` |
| null | `"null"` |
| object/array | **Error**: not supported as key |

Examples:
- `"customer_id": "C123"` → key bytes: `C123`
- `"amount": 123.45` → key bytes: `123.45`
- `"amount": 100` → key bytes: `100`
- `"active": true` → key bytes: `true`

### Composite Key Encoding

For multi-field keys, encode as a JSON array of canonical values:

```
--on "bank_code,account_number"
```

Given record: `{"bank_code": "B1", "account_number": 12345}`

Key string: `["B1","12345"]`

This is a JSON array where:
- String values are quoted
- Numbers are canonical decimal strings, quoted
- Order matches `--on` field order

### CLI Key Input

For `jn index get`:

```bash
# Single key
jn index get customers.jsonl --key customer_id --eq C123

# Composite key (JSON array)
jn index get txns.jsonl --key "bank,acct" --eq '["B1","12345"]'

# Multiple values (comma-separated for single key, newline-separated for composite)
jn index get customers.jsonl --key customer_id --eq "C123,C456,C789"

# Keys from stdin (one per line)
echo -e "C123\nC456" | jn index get customers.jsonl --key customer_id --stdin
```

---

## Staleness Detection

### Stored Source Identity

The header stores a complete source file identity:

| Field | Purpose |
|-------|---------|
| `source_size` | File size in bytes |
| `source_mtime_ns` | Modification time (nanoseconds since epoch) |
| `source_inode` | Inode number (Unix) or file index (Windows) |
| `source_dev` | Device ID |

### Freshness Check

```
fresh = (current_inode == stored_inode) AND
        (current_size == stored_size) AND
        (current_mtime_ns == stored_mtime_ns)
```

All three must match for the index to be considered fresh.

### Staleness Categories

| Condition | Category | Action |
|-----------|----------|--------|
| All match | Fresh | Use index |
| Size increased, inode same, mtime >= stored | Append-detected | Eligible for `update` |
| Size decreased | Modified | Full rebuild required |
| Inode changed | Replaced | Full rebuild required |
| mtime < stored | Backdated | Full rebuild required |

### Policy Flags

| Flag | Behavior |
|------|----------|
| (default) | Warn on stale, use index anyway for `get`; error for `join --right-index` |
| `--strict` | Error if stale |
| `--allow-stale` | Suppress warning, use stale index |

---

## CLI Commands

### `jn index build`

Build a lookup index for a NDJSON file.

```bash
# Basic usage
jn index build customers.jsonl --on customer_id

# Composite key
jn index build transactions.jsonl --on "bank_code,account_number"

# Unique mode (error if duplicate keys found)
jn index build customers.jsonl --on customer_id --mode unique

# Multi mode (default, multiple records per key allowed)
jn index build orders.jsonl --on customer_id --mode multi

# Custom output path
jn index build customers.jsonl --on customer_id --out /tmp/customers.idx

# Skip invalid JSON lines (default: error on invalid)
jn index build messy.jsonl --on id --skip-invalid

# Skip records with missing key (default: error)
jn index build messy.jsonl --on id --skip-missing-key
```

**Output (stderr, JSONL events):**

```json
{"event":"build_start","source":"customers.jsonl","key":"customer_id","mode":"multi"}
{"event":"progress","records_processed":10000,"keys_found":8500}
{"event":"build_complete","records":50000,"keys":42000,"postings":50000,"index_bytes":1048576,"duration_ms":234}
```

**Exit codes:**
- 0: Success
- 1: Build failed (I/O error, invalid JSON, duplicate key in unique mode)
- 2: Usage error

### `jn index get`

Lookup records by key.

```bash
# Single key lookup
jn index get customers.jsonl --key customer_id --eq C123

# Multiple values
jn index get customers.jsonl --key customer_id --eq "C123,C456,C789"

# Composite key
jn index get txns.jsonl --key "bank,acct" --eq '["B1","12345"]'

# Read keys from stdin
echo -e "C123\nC456" | jn index get customers.jsonl --key customer_id --stdin

# Strict mode (error if index stale or missing)
jn index get customers.jsonl --key customer_id --eq C123 --strict

# Allow stale index
jn index get customers.jsonl --key customer_id --eq C123 --allow-stale

# Fallback to scan if no index (default: error)
jn index get customers.jsonl --key customer_id --eq C123 --fallback scan
```

**Output (stdout):** Matching records as NDJSON

```json
{"customer_id":"C123","name":"Alice","region":"West"}
```

**Fallback behavior:**

| Condition | Default | With `--fallback scan` |
|-----------|---------|----------------------|
| Index missing | Error | Scan source file |
| Index stale | Warn + use | Warn + use |
| Index corrupt | Error | Scan source file |

**Events (stderr):**

```json
{"event":"index_stale","source":"customers.jsonl","reason":"source_modified"}
{"event":"fallback","mode":"scan","reason":"index_missing"}
```

### `jn index check`

Validate index integrity and freshness.

```bash
jn index check customers.jsonl --key customer_id
```

**Output:**

```json
{
  "valid": true,
  "fresh": true,
  "source": "customers.jsonl",
  "index": "customers.jsonl.jnx.customer_id",
  "key": "customer_id",
  "keys": 42000,
  "postings": 50000,
  "index_bytes": 1048576,
  "checksums_ok": true
}
```

If stale:

```json
{
  "valid": true,
  "fresh": false,
  "stale_reason": "source_size_changed",
  "source_size_stored": 52428800,
  "source_size_current": 53477376
}
```

If corrupt:

```json
{
  "valid": false,
  "error": "key_table_crc_mismatch",
  "expected_crc": "0xABCD1234",
  "actual_crc": "0xDEADBEEF"
}
```

### `jn index stats`

Show index statistics.

```bash
jn index stats customers.jsonl --key customer_id
```

**Output:**

```json
{
  "source": "customers.jsonl",
  "index": "customers.jsonl.jnx.customer_id",
  "key": "customer_id",
  "mode": "multi",
  "keys": 42000,
  "postings": 50000,
  "avg_postings_per_key": 1.19,
  "max_postings_per_key": 47,
  "index_bytes": 1048576,
  "source_bytes": 52428800,
  "overhead_ratio": 0.02,
  "build_timestamp": "2024-12-21T10:30:00Z",
  "fresh": true
}
```

### `jn index update`

Incremental update for append-only files.

```bash
jn index update customers.jsonl --key customer_id
```

**Behavior:**

1. Check if append-detected (size increased, inode same)
2. If yes: index new records, write delta file
3. If no: error with message to use `--full`

```bash
# Force full rebuild
jn index update customers.jsonl --key customer_id --full
```

**Events:**

```json
{"event":"update_mode","mode":"incremental","new_bytes":1048576,"estimated_new_records":1000}
{"event":"update_complete","new_keys":800,"new_postings":1000,"delta_bytes":16384}
```

Or if full rebuild required:

```json
{"event":"update_rejected","reason":"source_modified_not_appended","action":"use --full"}
```

### `jn graph expand`

Multi-hop graph traversal using lookup indexes.

```bash
# Basic expansion (requires edges.jsonl.jnx.from to exist)
jn graph expand edges.jsonl --seed "C123" --hops 3

# Reverse direction (requires edges.jsonl.jnx.to)
jn graph expand edges.jsonl --seed "C123" --hops 3 --reverse

# Filter by predicate field value
jn graph expand edges.jsonl --seed "C123" --hops 3 --pred-field pred --pred-value subClassOf

# Limit output nodes
jn graph expand edges.jsonl --seed "C123" --hops 3 --limit 1000

# Custom field names
jn graph expand edges.jsonl --seed "C123" --hops 3 \
  --from-field source --to-field target

# Seeds from stdin
jn cat seeds.jsonl | jn graph expand edges.jsonl --seed-field id --hops 2

# Strict mode (error if index missing)
jn graph expand edges.jsonl --seed "C123" --hops 3 --strict
```

**Output (stdout):**

```json
{"node":"C123","hop":0}
{"node":"C456","hop":1,"via_edge":{"from":"C123","pred":"subClassOf","to":"C456"}}
{"node":"C789","hop":2,"via_edge":{"from":"C456","pred":"subClassOf","to":"C789"}}
```

**Events (stderr):**

```json
{"event":"expand_start","seed":"C123","max_hops":3}
{"event":"expand_complete","nodes_visited":156,"edges_traversed":203,"duration_ms":45}
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
    ├── lookup.zig         # Lookup index build/query
    ├── format.zig         # Binary format constants and read/write
    ├── mmap.zig           # Memory mapping utilities
    ├── hash.zig           # xxh3_64 wrapper
    ├── key.zig            # Key encoding (canonical strings)
    ├── staleness.zig      # Source identity and freshness checks
    └── checksum.zig       # CRC32 utilities
```

### Public API

```zig
// jn-index/src/root.zig

pub const BuildOptions = struct {
    mode: enum { unique, multi } = .multi,
    skip_invalid_json: bool = false,
    skip_missing_key: bool = false,
    output_path: ?[]const u8 = null,
};

/// Build a lookup index
pub fn buildLookupIndex(
    allocator: Allocator,
    source_path: []const u8,
    key_fields: []const []const u8,  // ["customer_id"] or ["bank", "acct"]
    options: BuildOptions,
    progress_writer: ?std.fs.File.Writer,  // for JSONL events
) !BuildResult;

pub const BuildResult = struct {
    records_processed: u64,
    keys_found: u32,
    postings: u32,
    skipped_invalid: u32,
    skipped_missing_key: u32,
    index_bytes: u64,
    duration_ns: u64,
};

/// Open a lookup index for queries (memory-mapped)
pub fn openLookupIndex(index_path: []const u8) !LookupIndex;

pub const LookupIndex = struct {
    // Opaque handle to mmap'd data

    /// Check if index is fresh relative to source
    pub fn checkFreshness(self: *const LookupIndex, source_path: []const u8) FreshnessResult;

    pub const FreshnessResult = struct {
        fresh: bool,
        reason: ?[]const u8,  // "source_size_changed", "source_mtime_changed", etc.
    };

    /// Validate checksums
    pub fn validateChecksums(self: *const LookupIndex) ChecksumResult;

    pub const ChecksumResult = struct {
        valid: bool,
        failed_section: ?[]const u8,  // "key_table", "string_pool", etc.
    };

    /// Lookup postings for a key, returns iterator over source file offsets
    pub fn lookup(self: *const LookupIndex, key_bytes: []const u8) ?PostingIterator;

    pub const PostingIterator = struct {
        pub fn next(self: *PostingIterator) ?u64;  // source file byte offset
        pub fn count(self: *const PostingIterator) u32;
    };

    /// Get index statistics
    pub fn stats(self: *const LookupIndex) IndexStats;

    pub const IndexStats = struct {
        key_count: u32,
        posting_count: u32,
        index_bytes: u64,
        source_size: u64,
        build_timestamp_ns: u64,
    };

    /// Close and unmap
    pub fn close(self: *LookupIndex) void;
};

/// Encode a key value to canonical bytes
pub fn encodeKey(
    allocator: Allocator,
    json_value: std.json.Value,
) ![]const u8;

/// Encode composite key to canonical bytes
pub fn encodeCompositeKey(
    allocator: Allocator,
    json_values: []const std.json.Value,
) ![]const u8;
```

### Lookup Algorithm

```zig
pub fn lookup(self: *const LookupIndex, key_bytes: []const u8) ?PostingIterator {
    const hash = xxh3_64(key_bytes);

    // Binary search for first entry with matching hash
    var lo: u32 = 0;
    var hi: u32 = self.header.key_count;

    while (lo < hi) {
        const mid = lo + (hi - lo) / 2;
        const entry = self.getKeyEntry(mid);

        if (entry.key_hash < hash) {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }

    // Linear scan for exact key match (handles hash collisions)
    var i = lo;
    while (i < self.header.key_count) {
        const entry = self.getKeyEntry(i);

        if (entry.key_hash != hash) break;  // Past all entries with this hash

        const entry_key = self.getKeyString(entry);
        if (std.mem.eql(u8, entry_key, key_bytes)) {
            return PostingIterator{
                .offset_table = self.offset_table,
                .start = entry.posting_offset,
                .count = entry.posting_count,
                .current = 0,
            };
        }
        i += 1;
    }

    return null;  // Key not found
}
```

---

## Tool Integration

### `jn-join` Enhancement

Add `--right-index` flag for index-backed joins:

```bash
# Current: loads customers.jsonl into memory hash table
jn cat orders.jsonl | jn join customers.jsonl --on customer_id

# New: uses index, O(1) memory per lookup
jn cat orders.jsonl | jn join customers.jsonl --on customer_id --right-index
```

**Fallback behavior for `--right-index`:**

| Condition | Default | With `--fallback hash` |
|-----------|---------|----------------------|
| Index missing | **Error** | Fall back to hash join |
| Index stale | **Error** | Fall back to hash join |
| Index corrupt | **Error** | Fall back to hash join |

Rationale: Users specify `--right-index` because they need bounded memory. Silent fallback to hash join could cause OOM.

```bash
# Explicit fallback permission
jn cat orders.jsonl | jn join customers.jsonl --on customer_id \
  --right-index --fallback hash
```

**Implementation in `jn-join`:**

```zig
const JoinConfig = struct {
    // ... existing fields ...
    use_right_index: bool = false,
    fallback_to_hash: bool = false,
};

fn runJoin(allocator: Allocator, config: JoinConfig, right_source: []const u8) !void {
    if (config.use_right_index) {
        const index_path = try indexPathForKey(right_source, config.getRightKey());

        const index = jn_index.openLookupIndex(index_path) catch |err| {
            if (config.fallback_to_hash) {
                emitEvent(.{ .event = "fallback", .reason = "index_open_failed", .mode = "hash" });
                return runHashJoin(allocator, config, right_source);
            }
            return err;
        };
        defer index.close();

        const freshness = index.checkFreshness(right_source);
        if (!freshness.fresh) {
            if (config.fallback_to_hash) {
                emitEvent(.{ .event = "fallback", .reason = freshness.reason, .mode = "hash" });
                return runHashJoin(allocator, config, right_source);
            }
            return error.IndexStale;
        }

        return runIndexedJoin(allocator, config, right_source, &index);
    }

    return runHashJoin(allocator, config, right_source);
}
```

**Query stats event:**

```json
{"event":"join_stats","mode":"indexed","left_records":100000,"lookups":100000,"hits":95000,"source_seeks":95000,"duration_ms":1234}
```

### Orchestrator Routing

Add to `tools/zig/jn/main.zig`:

```zig
const subcommands = .{
    // ... existing ...
    .{ "index", "jn-index" },
    .{ "graph", "jn-graph" },
};
```

---

## Build Algorithm

### Memory Model

| Phase | Memory Usage |
|-------|--------------|
| **Query** | O(1) - mmap'd, only touched pages loaded |
| **Build** | O(keys + postings) - accumulates in memory |

**Build memory** scales with dataset size. For a file with K unique keys and P total postings:
- Key entries: 24 bytes × K
- Key strings: ~average_key_length × K
- Postings: 8 bytes × P
- Working buffers: ~1MB

For typical datasets (<10M records), this fits in RAM. For larger datasets, v2 can add external-memory sort.

### Build Steps

1. **Pass 1: Scan and accumulate**
   - Stream source file line by line
   - Parse JSON, extract key field(s)
   - Encode key to canonical bytes
   - Compute hash
   - Store `(hash, key_bytes, source_offset)` in memory

2. **Sort**
   - Sort accumulated entries by `(hash, key_bytes)`

3. **Deduplicate and build tables**
   - Merge entries with same key
   - Build key table (deduplicated)
   - Build string pool
   - Build offset table (postings)

4. **Write index**
   - Write header
   - Write key table
   - Write string pool
   - Write offset table
   - Compute and write checksums

5. **Atomic swap**
   - Write to `.tmp` file
   - Rename to final path

### Line Reading

- Records end at `\n` (or `\r\n`, with `\r` stripped)
- Maximum line length: 8MB (configurable via `--max-line-bytes`)
- Lines exceeding max are skipped with warning

---

## Incremental Updates

### Delta File Format

When source has only appended data:

```
customers.jsonl.jnx.customer_id         # base index
customers.jsonl.jnx.customer_id.delta   # delta index (same format)
```

Delta index covers only the appended portion of the source file.

### Query with Delta

When both base and delta exist:

1. Lookup in base index
2. Lookup in delta index
3. Concatenate postings (delta postings come after base)

### Compaction

```bash
jn index compact customers.jsonl --key customer_id
```

Merges base + delta into new base, deletes delta.

### Update Detection

```
append_detected = (current_inode == stored_inode) AND
                  (current_size > stored_size) AND
                  (current_mtime_ns >= stored_mtime_ns)
```

If append detected:
- Build delta index starting at `stored_size` offset
- Store `stored_size` as delta's "start offset" in header

If not append detected:
- Require `--full` flag for rebuild

---

## Error Handling

### JSON Parsing

| Mode | Invalid JSON Line | Missing Key Field |
|------|-------------------|-------------------|
| Default (strict) | **Error**, abort build | **Error**, abort build |
| `--skip-invalid` | Skip, count in stats | - |
| `--skip-missing-key` | - | Skip, count in stats |

Build completion reports skipped counts:

```json
{"event":"build_complete","records":50000,"keys":42000,"skipped_invalid":3,"skipped_missing_key":12}
```

### Index Validation

On `jn index check` or when opening index:

1. **Magic/version check**: Verify header magic and version
2. **Bounds check**: All offsets within file size
3. **Checksum verification**: CRC32 of each section

Validation failures:

```json
{"event":"index_corrupt","section":"key_table","error":"crc_mismatch"}
```

### Corruption Recovery

When corruption detected:
1. Emit error event
2. If `--auto-rebuild`: delete corrupt index, rebuild
3. Else: return error

```bash
# Enable auto-rebuild on corruption
jn index get customers.jsonl --key customer_id --eq C123 --auto-rebuild
```

---

## Implementation Phases

### Phase 1: Core Index Library

**Goal:** Build and query lookup indexes

- [ ] Create `libs/zig/jn-index/` library structure
- [ ] Implement format constants (`format.zig`)
- [ ] Implement xxh3_64 hash wrapper (`hash.zig`)
- [ ] Implement key encoding (`key.zig`)
- [ ] Implement mmap utilities (`mmap.zig`)
- [ ] Implement CRC32 checksum (`checksum.zig`)
- [ ] Implement staleness detection (`staleness.zig`)
- [ ] Implement lookup index build (`lookup.zig`)
- [ ] Implement lookup index query
- [ ] Unit tests for all components

**Deliverable:** Working `jn_index.buildLookupIndex()` and `jn_index.openLookupIndex()`

### Phase 2: CLI Tool

**Goal:** User-facing index commands

- [ ] Create `tools/zig/jn-index/` tool
- [ ] Implement `build` subcommand
- [ ] Implement `get` subcommand
- [ ] Implement `check` subcommand
- [ ] Implement `stats` subcommand
- [ ] Add to orchestrator routing
- [ ] Integration tests

**Deliverable:** Working `jn index build`, `jn index get`, `jn index check`, `jn index stats`

### Phase 3: Join Integration

**Goal:** Index-backed joins

- [ ] Add `--right-index` flag to `jn-join`
- [ ] Implement indexed join path
- [ ] Implement explicit fallback modes
- [ ] Emit query stats events
- [ ] Benchmark vs hash join

**Deliverable:** `jn join --right-index` working with predictable fallback

### Phase 4: Graph Expansion

**Goal:** Multi-hop traversal using lookup indexes

- [ ] Create `tools/zig/jn-graph/` tool
- [ ] Implement `expand` command using lookup indexes
- [ ] Support `--reverse` for incoming edges
- [ ] Support predicate filtering
- [ ] Support seed from stdin
- [ ] Integration tests

**Deliverable:** Working `jn graph expand`

### Phase 5: Incremental Updates

**Goal:** Efficient append-only updates

- [ ] Implement append detection
- [ ] Implement delta index build
- [ ] Implement delta-aware query
- [ ] Implement `compact` command
- [ ] Handle non-append modifications

**Deliverable:** Working `jn index update` and `jn index compact`

### Phase 6: Documentation & Polish

- [ ] Rename `spec/indexes` to `spec/16-indexes.md`
- [ ] Update `CLAUDE.md` with new commands
- [ ] Performance benchmarks with results
- [ ] Error message review
- [ ] Edge case testing

---

## Performance Targets

### Definitions

- **Cold**: Index file not in OS page cache, local SSD
- **Warm**: Index file in OS page cache
- **Lookup latency**: Time to return first posting (excludes source file read and JSON output)

### Lookup Index

| Metric | Target | Measurement |
|--------|--------|-------------|
| Build throughput | >100k records/sec | Single-threaded, SSD |
| Index overhead | <5% of source size | Typical key distribution |
| Cold lookup | <10ms | 1M key index, SSD |
| Warm lookup | <0.1ms | 1M key index, cached |
| Query memory | <10MB | Regardless of index size |

### Graph Expansion

| Metric | Target | Measurement |
|--------|--------|-------------|
| Single hop (out) | <5ms warm | Per node, excludes I/O |
| 3-hop expansion | <100ms warm | 1000 result nodes |
| Memory | <20MB | Regardless of graph size |

### Indexed Join

| Metric | Target | Measurement |
|--------|--------|-------------|
| Throughput | >50k joins/sec | With warm index |
| Memory | O(1) | Per-record, not O(right-side) |

### Query Stats Event

All queries emit stats to stderr:

```json
{"event":"query_stats","operation":"get","lookups":1,"hits":1,"source_reads":1,"bytes_read":234,"duration_ms":2}
{"event":"query_stats","operation":"join","left_records":100000,"lookups":100000,"hits":95000,"duration_ms":1500}
{"event":"query_stats","operation":"expand","seed":"C123","hops":3,"nodes":156,"edges":203,"duration_ms":45}
```

---

## Design Decisions

### Why Binary Format, Not SQLite?

| Factor | Binary | SQLite |
|--------|--------|--------|
| Dependency | None | ~1MB library |
| mmap efficiency | Direct | Has overhead |
| Build complexity | Low | Higher |
| Feature scope | Minimal | Too much |

JN Indexes are intentionally minimal. SQLite would be overkill.

### Why xxh3_64?

- Extremely fast (>10 GB/s)
- 64-bit output (collision probability ~1/2^64)
- Modern, well-tested algorithm
- Single-include implementation available

### Why Sorted Keys + Binary Search (Not Hash Table)?

- Predictable O(log n) lookup
- Cache-friendly sequential access after binary search
- Simple to mmap
- Handles collisions naturally (linear scan of same-hash entries)
- Hash table would require more complex memory layout

### Why File Offsets, Not Record Copies?

- **Smaller indexes**: 8 bytes per posting vs average record size
- **Always current**: Reads from source, not stale copy
- **Simpler updates**: Append new offsets, don't duplicate data

Trade-off: Requires seek + read from source file. Acceptable because:
- SSD random read is fast
- OS page cache helps for repeated access
- Source file is typically sequential on disk

### Why Explicit Fallback Modes?

Users choose `--right-index` for predictable memory. Silent fallback to hash join violates that contract. Explicit `--fallback hash` lets users opt-in to degraded mode.

---

## File Inventory

### New Files

```
libs/zig/jn-index/
├── build.zig
├── build.zig.zon
└── src/
    ├── root.zig
    ├── lookup.zig
    ├── format.zig
    ├── mmap.zig
    ├── hash.zig
    ├── key.zig
    ├── staleness.zig
    └── checksum.zig

tools/zig/jn-index/
├── build.zig
├── build.zig.zon
└── main.zig

tools/zig/jn-graph/
├── build.zig
├── build.zig.zon
└── main.zig
```

### Modified Files

```
tools/zig/jn/main.zig          # Add index, graph routing
tools/zig/jn-join/main.zig     # Add --right-index, --fallback
Makefile                        # Add new build targets
CLAUDE.md                       # Document new commands
spec/indexes → spec/16-indexes.md  # Rename with number
```

---

## Summary

JN Indexes provide fast key lookups and graph traversals while preserving JN's core properties:

- **NDJSON canonical**: Indexes are derived, disposable
- **Streaming output**: Queries emit NDJSON line-by-line
- **Predictable resources**: Query memory bounded via mmap
- **Explicit behavior**: Fallback modes are opt-in
- **Composable**: Integrates with existing pipeline tools

Key implementation choices:
- Binary format with CRC32 checksums
- xxh3_64 hashing with sorted key table
- Canonical key encoding (JSON array for composite)
- Inode + size + mtime_ns for staleness
- Graph traversal via lookup indexes (v1)
- Delta files for incremental updates
