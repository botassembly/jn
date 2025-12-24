# JN Index Design

> **Purpose**: Implementation design for fast NDJSON lookup indexes

This document provides the detailed implementation design for JN Indexes, which enable O(1) key lookups and graph traversals on NDJSON files without scanning.

---

## Table of Contents

1. [Overview](#overview)
2. [Index File Naming](#index-file-naming)
3. [Lookup Index Format](#lookup-index-format)
4. [Staleness and Freshness](#staleness-and-freshness)
5. [Key Encoding](#key-encoding)
6. [Graph Traversal Strategy](#graph-traversal-strategy)
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
edges.jsonl.jnx.from+pred               # composite for predicate-filtered traversal
```

### Delta Files

Incremental updates produce delta files with `.delta` suffix:

```
customers.jsonl.jnx.customer_id         # base index
customers.jsonl.jnx.customer_id.delta   # delta index (same format)
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
│                        HEADER (136 bytes)                  │
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

### Header (136 bytes, offset 0)

All integers are little-endian.

```
Offset  Size  Field                  Description
------  ----  -----                  -----------
0       4     magic                  "JNX\x03" (version 3)
4       4     version                3 (u32)
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
112     8     coverage_start         Source byte offset where this index starts (u64)
120     8     coverage_end           Source byte offset where this index ends (u64)
128     8     coverage_tail_hash64   xxh3_64 of last min(64KB, coverage_end - coverage_start) bytes
```

**Coverage range**: For a base index, `coverage_start=0` and `coverage_end=source_size`. For a delta index, `coverage_start=base.coverage_end` and `coverage_end=current_source_size`.

**Boundary fingerprint**: `coverage_tail_hash64` is the xxh3_64 hash of the last min(64KB, covered_bytes) of the covered region. This enables verification that the covered prefix is unchanged, upgrading "append-detected" from a heuristic to a guardrail.

**Magic/version validation**: Both must match exactly. If magic is wrong, the file is not a JNX index. If version differs, the format is incompatible.

### Key Table

Location: `[key_table_offset, key_table_offset + key_table_size)`

Sorted array of key entries. **Sort order**:
1. Primary: `key_hash` ascending
2. Secondary: key bytes lexicographic ascending
3. Tertiary: key length ascending (to disambiguate prefix-equal memcmp comparisons)

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

Array of source file byte offsets (u64 each), **sorted ascending within each key's posting list**:

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

**Posting order**: Within each key's posting list, offsets are sorted ascending by source file position. This ensures sequential reads when fetching multiple records for the same key.

### Checksum Section (16 bytes)

Location: last 16 bytes of file

```
Offset  Size  Field              Description
------  ----  -----              -----------
0       4     key_table_crc32    CRC32 of key table bytes
4       4     string_pool_crc32  CRC32 of string pool bytes
8       4     offset_table_crc32 CRC32 of offset table bytes
12      4     header_crc32       CRC32 of header bytes (0-135)
```

CRC32 uses IEEE polynomial (same as zlib).

**Validation policy**: See [Index Validation](#index-validation) for when checksums are verified.

---

## Staleness and Freshness

### Stored Source Identity

The header stores a complete source file identity:

| Field | Purpose |
|-------|---------|
| `source_size` | File size in bytes at build time |
| `source_mtime_ns` | Modification time (nanoseconds since epoch) |
| `source_inode` | Inode number (Unix) or file index (Windows) |
| `source_dev` | Device ID |
| `coverage_start` | First byte of source covered by this index |
| `coverage_end` | Last byte (exclusive) of source covered |

### Single Index Freshness

For a single index file (no delta):

```
fresh = (current_inode == stored_inode) AND
        (current_dev == stored_dev) AND
        (current_size == coverage_end) AND
        (current_mtime_ns == stored_mtime_ns)
```

### Index Set Freshness (with Delta)

When both base and delta exist, treat them as a set:

```
base:  file.jnx.key
delta: file.jnx.key.delta
```

The set is **fresh** when:

```
fresh_set = (base.coverage_start == 0) AND
            (base.coverage_end == delta.coverage_start) AND
            (delta.coverage_end == current_size) AND
            (base.source_inode == current_inode) AND
            (base.source_dev == current_dev) AND
            (delta.source_inode == current_inode) AND
            (delta.source_dev == current_dev) AND
            (delta.source_mtime_ns == current_mtime_ns)
```

This means:
- Base covers `[0, N)`
- Delta covers `[N, current_size)`
- Together they cover the entire current file
- Both base and delta refer to the same file (inode/dev match)
- Delta's mtime matches current file (base mtime need not match)

**No warning spam**: When `fresh_set` is true, queries should not warn about staleness, even though the base index alone would appear stale.

### Staleness Categories

| Condition | Category | Safety | Default Action |
|-----------|----------|--------|----------------|
| All match | Fresh | Safe | Use index |
| Size increased, inode/dev same, mtime >= stored, tail hash matches | Append-verified | Safe (subset) | Warn once, use (results may be incomplete) |
| Size increased, inode/dev same, mtime >= stored, tail hash mismatch | Modified | **Unsafe** | Error |
| Size decreased | Truncated | **Unsafe** | Error |
| Inode changed | Replaced | **Unsafe** | Error |
| mtime < stored | Backdated | **Unsafe** | Error |
| Size same, mtime changed | Modified-in-place | **Unsafe** | Error |

**Append verification**: When size has increased, we verify `coverage_tail_hash64` by re-hashing the last min(64KB, coverage_end - coverage_start) bytes of the current file at the same positions. If the hash matches, the covered prefix is unchanged and append-only behavior is confirmed. If the hash mismatches, the file was modified in-place.

### Default Behavior by Command

**`jn index get`:**

| Category | Default | With `--allow-stale` |
|----------|---------|---------------------|
| Fresh / Fresh-set | Use | Use |
| Append-verified | Warn once + use | Use (no warn) |
| Unsafe (truncated/replaced/backdated/modified) | **Error** | Use (warn) |

**`jn join --right-index`:**

| Category | Default | With `--fallback hash` |
|----------|---------|----------------------|
| Fresh / Fresh-set | Use | Use |
| Any stale | **Error** | Fall back to hash join |

**`jn graph expand`:**

| Category | Default | With `--allow-stale` |
|----------|---------|---------------------|
| Fresh / Fresh-set | Use | Use |
| Any stale | **Error** | Use (warn) |

### Policy Flags

| Flag | Behavior |
|------|----------|
| `--strict` | Error on any non-fresh (even append-detected) |
| `--allow-stale` | Suppress errors, warn and use stale index |

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
| number | **Lexical token** from JSON source (see below) |
| boolean | `"true"` or `"false"` |
| null | `"null"` |
| object/array | **Error**: not supported as key |

### Number Canonicalization: Lexical Token

Numbers are encoded as **the exact lexical token from the JSON input**, not a re-rendered float.

**Rationale**: Avoids float rounding issues, exponent format ambiguity, and cross-implementation differences.

**During build**:
- When parsing JSON, capture the raw byte slice for the number token
- Use those exact bytes as the key

**During query (CLI input)**:
- Accept the exact token bytes as provided by the user
- `--eq 123.45` matches records where the JSON source contained `123.45`
- `--eq 1.2345e2` matches records where the JSON source contained `1.2345e2`

**Implication**: `123.0` and `123` are different keys (they have different lexical representations).

**Recommendation**: For join keys, prefer string fields. If using numeric keys, ensure consistent formatting in source data.

### Composite Key Encoding

For multi-field keys, encode as a JSON array of **string** elements:

```
--on "bank_code,account_number"
```

Given record: `{"bank_code": "B1", "account_number": 12345}`

Key string: `["B1","12345"]`

Rules:
- Each field value is converted to its canonical string (as above)
- The canonical string is then JSON-escaped and quoted
- Elements are ordered by `--on` field order
- Result is a valid JSON array

Examples:
- `bank_code="B1"`, `account_number=12345` → `["B1","12345"]`
- `active=true`, `region="West"` → `["true","West"]`
- `code=null`, `id="X"` → `["null","X"]`

### CLI Key Input

For `jn index get`:

```bash
# Single key
jn index get customers.jsonl --key customer_id --eq C123

# Multiple values (comma-separated)
jn index get customers.jsonl --key customer_id --eq "C123,C456,C789"

# Multiple values (repeated flag, avoids comma ambiguity)
jn index get customers.jsonl --key customer_id --eq C123 --eq C456

# Composite key (JSON array)
jn index get txns.jsonl --key "bank,acct" --eq '["B1","12345"]'

# Keys from stdin (one per line, robust for any key content)
echo -e "C123\nC456" | jn index get customers.jsonl --key customer_id --stdin
```

**Note**: `--stdin` is the robust method when keys may contain commas.

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

### Memory Constraints

Graph traversal requires:
- **Frontier queue**: Nodes to visit at current/next hop
- **Visited set**: Nodes already seen (to avoid cycles)

Memory scales with visited node count, **not** graph size.

**Required limit**: `--limit` controls maximum nodes emitted (default: 10000).

When limit is reached:
```json
{"event":"expand_truncated","reason":"limit_reached","limit":10000,"nodes_visited":10000}
```

### Composite Index Optimization for Predicate Filtering

When traversing with a predicate filter:

```bash
jn graph expand edges.jsonl --seed "C123" --hops 3 --pred-field pred --pred-value subClassOf
```

**Without optimization**: Lookup all edges from node, parse each, filter by predicate.

**With composite index**: Build `edges.jsonl.jnx.from+pred`, then lookup composite key `["C123","subClassOf"]` directly.

```bash
# Build composite index for predicate-filtered traversal
jn index build edges.jsonl --on "from,pred"

# Traversal automatically uses it when available
jn graph expand edges.jsonl --seed "C123" --hops 3 --pred-value subClassOf
```

**Behavior**: `jn graph expand` checks for `from+pred` index first. If present, uses composite lookups. Otherwise falls back to filter-after-lookup.

**Reverse traversal with predicate filter**: When using `--reverse` with predicate filtering, `jn graph expand` checks for `to+pred` index:

```bash
# Build composite index for reverse predicate-filtered traversal
jn index build edges.jsonl --on "to,pred"

# Traversal automatically uses it
jn graph expand edges.jsonl --seed "C123" --hops 3 --reverse --pred-value subClassOf
```

**Recommendation**: For heavy single-predicate traversals, build the appropriate composite index:
- Forward: `--on "from,pred"`
- Reverse: `--on "to,pred"`

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

# Custom max line length (default: 8MB)
jn index build huge.jsonl --on id --max-line-bytes=16777216
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

# Multiple values (comma-separated)
jn index get customers.jsonl --key customer_id --eq "C123,C456,C789"

# Multiple values (repeated flag)
jn index get customers.jsonl --key customer_id --eq C123 --eq C456

# Composite key
jn index get txns.jsonl --key "bank,acct" --eq '["B1","12345"]'

# Read keys from stdin (robust for keys with commas)
echo -e "C123\nC456" | jn index get customers.jsonl --key customer_id --stdin

# Strict mode (error if any staleness)
jn index get customers.jsonl --key customer_id --eq C123 --strict

# Allow unsafe stale (truncated/replaced/modified)
jn index get customers.jsonl --key customer_id --eq C123 --allow-stale

# Fallback to scan if no index (default: error)
jn index get customers.jsonl --key customer_id --eq C123 --fallback scan

# Verify checksums before query
jn index get customers.jsonl --key customer_id --eq C123 --verify
```

**Output (stdout):** Matching records as NDJSON.

```json
{"customer_id":"C123","name":"Alice","region":"West"}
```

**Output ordering**: When multiple keys are provided, results are grouped by key in input order (`--eq` order, then stdin order). Within each key, records are emitted in source file order.

**Fallback behavior:**

| Condition | Default | With `--fallback scan` |
|-----------|---------|----------------------|
| Index missing | Error | Scan source file |
| Index corrupt | Error | Scan source file |
| Append-detected | Warn once + use | Warn once + use |
| Unsafe stale | Error | Error (use `--allow-stale`) |

**Events (stderr):**

```json
{"event":"index_stale","source":"customers.jsonl","category":"append_detected"}
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
  "coverage_start": 0,
  "coverage_end": 52428800,
  "index_bytes": 1048576,
  "checksums_ok": true
}
```

If stale:

```json
{
  "valid": true,
  "fresh": false,
  "stale_category": "append_detected",
  "coverage_end": 52428800,
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

**Note**: `jn index check` always verifies full checksums.

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
  "coverage_start": 0,
  "coverage_end": 52428800,
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
{"event":"update_rejected","reason":"source_modified_not_appended","category":"truncated","action":"use --full"}
```

### `jn index compact`

Merge base and delta into single index.

```bash
jn index compact customers.jsonl --key customer_id
```

Merges `customers.jsonl.jnx.customer_id` and `customers.jsonl.jnx.customer_id.delta` into a new base, then deletes delta.

### `jn graph expand`

Multi-hop graph traversal using lookup indexes.

```bash
# Basic expansion (requires edges.jsonl.jnx.from to exist)
jn graph expand edges.jsonl --seed "C123" --hops 3

# Reverse direction (requires edges.jsonl.jnx.to)
jn graph expand edges.jsonl --seed "C123" --hops 3 --reverse

# Filter by predicate (uses edges.jsonl.jnx.from+pred if available)
jn graph expand edges.jsonl --seed "C123" --hops 3 --pred-field pred --pred-value subClassOf

# Limit output nodes (default: 10000)
jn graph expand edges.jsonl --seed "C123" --hops 3 --limit 1000

# Custom field names
jn graph expand edges.jsonl --seed "C123" --hops 3 \
  --from-field source --to-field target

# Seeds from stdin
jn cat seeds.jsonl | jn graph expand edges.jsonl --seed-field id --hops 2

# Strict mode (error if index missing or stale)
jn graph expand edges.jsonl --seed "C123" --hops 3 --strict

# Allow stale index
jn graph expand edges.jsonl --seed "C123" --hops 3 --allow-stale
```

**Output (stdout):**

```json
{"node":"C123","hop":0}
{"node":"C456","hop":1,"via_edge":{"from":"C123","pred":"subClassOf","to":"C456"}}
{"node":"C789","hop":2,"via_edge":{"from":"C456","pred":"subClassOf","to":"C789"}}
```

**Events (stderr):**

```json
{"event":"expand_start","seed":"C123","max_hops":3,"limit":10000}
{"event":"expand_complete","nodes_visited":156,"edges_traversed":203,"duration_ms":45}
```

Or if truncated:

```json
{"event":"expand_truncated","reason":"limit_reached","limit":10000,"nodes_visited":10000}
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
    max_line_bytes: usize = 8 * 1024 * 1024,  // 8MB default
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
    skipped_line_too_long: u32,
    index_bytes: u64,
    duration_ns: u64,
};

/// Open a lookup index for queries (memory-mapped)
pub fn openLookupIndex(index_path: []const u8) !LookupIndex;

pub const LookupIndex = struct {
    // Opaque handle to mmap'd data

    /// Check if index is fresh relative to source (cheap, no CRC)
    pub fn checkFreshness(self: *const LookupIndex, source_path: []const u8) FreshnessResult;

    pub const FreshnessResult = struct {
        fresh: bool,
        category: ?StalenessCategory,
    };

    pub const StalenessCategory = enum {
        append_verified,  // Safe: tail hash matches, subset results
        modified,         // Unsafe: tail hash mismatch or in-place edit
        truncated,        // Unsafe: offsets may be invalid
        replaced,         // Unsafe: different file
        backdated,        // Unsafe: suspicious
    };

    /// Validate structure (cheap: magic, version, bounds, header CRC only)
    pub fn validateStructure(self: *const LookupIndex) StructureResult;

    /// Validate full checksums (expensive: reads all sections)
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
        coverage_start: u64,
        coverage_end: u64,
        build_timestamp_ns: u64,
    };

    /// Close and unmap
    pub fn close(self: *LookupIndex) void;
};

/// Index set: base + optional delta, treated as a unit
/// All delta-aware consumers should use this instead of LookupIndex directly
pub const LookupIndexSet = struct {
    base: LookupIndex,
    delta: ?LookupIndex,

    /// Open an index set (auto-detects .delta file)
    pub fn open(base_path: []const u8) !LookupIndexSet;

    /// Check freshness of the set (uses fresh_set logic when delta exists)
    pub fn checkFreshnessSet(self: *const LookupIndexSet, source_path: []const u8) FreshnessSetResult;

    pub const FreshnessSetResult = struct {
        fresh: bool,
        category: ?StalenessCategory,
        has_delta: bool,
    };

    /// Lookup with merged postings (base first, then delta)
    pub fn lookupMerged(self: *const LookupIndexSet, key_bytes: []const u8) ?MergedPostingIterator;

    pub const MergedPostingIterator = struct {
        pub fn next(self: *MergedPostingIterator) ?u64;
        pub fn count(self: *const MergedPostingIterator) u32;
    };

    /// Get combined statistics
    pub fn statsSet(self: *const LookupIndexSet) IndexSetStats;

    pub const IndexSetStats = struct {
        base_keys: u32,
        delta_keys: u32,
        total_postings: u32,
        coverage_start: u64,
        coverage_end: u64,
        has_delta: bool,
    };

    /// Close both base and delta
    pub fn close(self: *LookupIndexSet) void;
};

/// Encode a key value to canonical bytes (captures lexical token for numbers)
pub fn encodeKey(
    allocator: Allocator,
    json_value: std.json.Value,
    raw_token: ?[]const u8,  // For numbers: the original lexical token
) ![]const u8;

/// Encode composite key to canonical bytes
pub fn encodeCompositeKey(
    allocator: Allocator,
    json_values: []const std.json.Value,
    raw_tokens: []const ?[]const u8,
) ![]const u8;
```

### Index Validation

**On open (always, cheap):**
- Magic bytes match "JNX\x03"
- Version matches 3
- Header CRC32 valid
- Bounds check: all offsets within file size
- Consistency: sizes match counts
- Tail hash verification (for append detection)

**On `--verify` or `jn index check` (expensive):**
- Full CRC32 of key table, string pool, offset table

**Rationale**: Computing CRCs on large offset tables would kill startup latency. Structural validation catches most corruption; full CRC is opt-in.

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
| Index stale (any category) | **Error** | Fall back to hash join |
| Index corrupt | **Error** | Fall back to hash join |

Rationale: Users specify `--right-index` because they need bounded memory. Silent fallback to hash join could cause OOM.

```bash
# Explicit fallback permission
jn cat orders.jsonl | jn join customers.jsonl --on customer_id \
  --right-index --fallback hash

# Verify index checksums before join
jn cat orders.jsonl | jn join customers.jsonl --on customer_id \
  --right-index --verify-index
```

**Implementation in `jn-join`:**

Uses `LookupIndexSet` to handle base + delta correctly:

```zig
const JoinConfig = struct {
    // ... existing fields ...
    use_right_index: bool = false,
    fallback_to_hash: bool = false,
    verify_index: bool = false,
};

fn runJoin(allocator: Allocator, config: JoinConfig, right_source: []const u8) !void {
    if (config.use_right_index) {
        const index_path = try indexPathForKey(right_source, config.getRightKey());

        // Use LookupIndexSet to handle base + delta
        var index_set = jn_index.LookupIndexSet.open(index_path) catch |err| {
            if (config.fallback_to_hash) {
                emitEvent(.{ .event = "fallback", .reason = "index_open_failed", .mode = "hash" });
                return runHashJoin(allocator, config, right_source);
            }
            return err;
        };
        defer index_set.close();

        if (config.verify_index) {
            // Verify both base and delta checksums
            const base_crc = index_set.base.validateChecksums();
            if (!base_crc.valid) {
                if (config.fallback_to_hash) {
                    emitEvent(.{ .event = "fallback", .reason = "base_checksum_failed", .mode = "hash" });
                    return runHashJoin(allocator, config, right_source);
                }
                return error.IndexCorrupt;
            }
            if (index_set.delta) |*delta| {
                const delta_crc = delta.validateChecksums();
                if (!delta_crc.valid) {
                    if (config.fallback_to_hash) {
                        emitEvent(.{ .event = "fallback", .reason = "delta_checksum_failed", .mode = "hash" });
                        return runHashJoin(allocator, config, right_source);
                    }
                    return error.IndexCorrupt;
                }
            }
        }

        // Check set freshness (handles fresh_set logic when delta exists)
        const freshness = index_set.checkFreshnessSet(right_source);
        if (!freshness.fresh) {
            if (config.fallback_to_hash) {
                emitEvent(.{ .event = "fallback", .reason = @tagName(freshness.category.?), .mode = "hash" });
                return runHashJoin(allocator, config, right_source);
            }
            return error.IndexStale;
        }

        return runIndexedJoin(allocator, config, right_source, &index_set);
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
   - Capture lexical token for number keys
   - Encode key to canonical bytes
   - Compute hash
   - Store `(hash, key_bytes, source_offset)` in memory

2. **Sort**
   - Sort accumulated entries by `(hash, key_bytes, source_offset)`
   - Tertiary sort by `source_offset` ensures postings are in file order

3. **Deduplicate and build tables**
   - Merge entries with same key
   - Build key table (deduplicated)
   - Build string pool
   - Build offset table (postings in source order)

4. **Write index**
   - Write header (with coverage_start=0, coverage_end=source_size)
   - Write key table
   - Write string pool
   - Write offset table
   - Compute and write checksums

5. **Atomic swap**
   - Write to `.tmp` file
   - Rename to final path

### Line Reading

- Records end at `\n` (or `\r\n`, with `\r` stripped)
- Maximum line length: 8MB default (configurable via `--max-line-bytes`)
- Lines exceeding max: **error** by default (use `--skip-invalid` to skip with warning)

---

## Incremental Updates

### Delta File Format

When source has only appended data:

```
customers.jsonl.jnx.customer_id         # base index (coverage: [0, N))
customers.jsonl.jnx.customer_id.delta   # delta index (coverage: [N, M))
```

Delta index has same format as base, with:
- `coverage_start = base.coverage_end`
- `coverage_end = current_source_size`

### Single-Delta Policy

**At most one delta segment per index.** If `.delta` already exists and the file appends again, `jn index update` rebuilds the delta to cover `[base.coverage_end, current_size)`, atomically replacing the prior delta.

This avoids multi-segment manifests and keeps `fresh_set` logic simple.

### Query with Delta

When both base and delta exist, tools use `LookupIndexSet`:

1. Check set freshness (base + delta cover current file)
2. For each key lookup:
   - Lookup in base index
   - Lookup in delta index
   - Concatenate postings (base postings first, then delta)
3. Return merged results in source file order

### Compaction

```bash
jn index compact customers.jsonl --key customer_id
```

1. Read current source file
2. Build new base index covering [0, current_size)
3. Atomic swap to replace old base
4. Delete delta file

### Update Detection

```
append_verified = (current_inode == stored_inode) AND
                  (current_dev == stored_dev) AND
                  (current_size > coverage_end) AND
                  (current_mtime_ns >= stored_mtime_ns) AND
                  (coverage_tail_hash64 matches re-computed hash)
```

If append verified:
- Build delta index starting at `coverage_end` offset
- Store `coverage_start=base.coverage_end`, `coverage_end=current_size`
- If delta already exists, replace it (single-delta policy)

If not append verified (tail hash mismatch or other modification):
- Require `--full` flag for rebuild

---

## Error Handling

### JSON Parsing

| Mode | Invalid JSON Line | Missing Key Field | Line Too Long |
|------|-------------------|-------------------|---------------|
| Default (strict) | **Error**, abort | **Error**, abort | **Error**, abort |
| `--skip-invalid` | Skip, count | **Error**, abort | Skip, count |
| `--skip-missing-key` | **Error**, abort | Skip, count | **Error**, abort |
| Both flags | Skip, count | Skip, count | Skip, count |

**Note**: The flags are independent. `--skip-invalid` handles malformed JSON and oversized lines. `--skip-missing-key` handles records where the indexed field is absent.

Build completion reports skipped counts:

```json
{"event":"build_complete","records":50000,"keys":42000,"skipped_invalid":3,"skipped_missing_key":12,"skipped_line_too_long":0}
```

### Index Validation

**On open (always, cheap):**

1. **Magic check**: Must be "JNX\x03"
2. **Version check**: Must be 3
3. **Header CRC**: Verify header_crc32

4. **Structural invariants** (bounds and consistency checks):
   ```
   file_size >= 136 + 16
   key_table_offset + key_table_size <= file_size - 16
   string_pool_offset + string_pool_size <= file_size - 16
   offset_table_offset + offset_table_size <= file_size - 16
   key_table_size == key_count * 24
   offset_table_size == posting_count * 8
   coverage_start <= coverage_end <= source_size
   (for base index) coverage_start == 0
   ```

5. **Key entry bounds** (for each key entry):
   ```
   string_offset + string_length <= string_pool_size
   posting_offset + posting_count <= posting_count_total
   ```

**On `--verify` or `jn index check` (expensive):**

6. **Section CRCs**: Verify key_table_crc32, string_pool_crc32, offset_table_crc32

Validation failures:

```json
{"event":"index_invalid","error":"magic_mismatch"}
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
- [ ] Implement key encoding with lexical token capture (`key.zig`)
- [ ] Implement mmap utilities (`mmap.zig`)
- [ ] Implement CRC32 checksum (`checksum.zig`)
- [ ] Implement staleness detection with categories and tail hash (`staleness.zig`)
- [ ] Implement lookup index build with coverage range and tail hash (`lookup.zig`)
- [ ] Implement lookup index query
- [ ] Implement LookupIndexSet for base + delta (`index_set.zig`)
- [ ] Implement structural validation (cheap) vs full CRC (opt-in)
- [ ] Unit tests for all components

**Deliverable:** Working `jn_index.buildLookupIndex()`, `jn_index.openLookupIndex()`, and `jn_index.LookupIndexSet`

### Phase 2: CLI Tool

**Goal:** User-facing index commands

- [ ] Create `tools/zig/jn-index/` tool
- [ ] Implement `build` subcommand
- [ ] Implement `get` subcommand with staleness categories
- [ ] Implement `check` subcommand (full CRC)
- [ ] Implement `stats` subcommand
- [ ] Add to orchestrator routing
- [ ] Integration tests

**Deliverable:** Working `jn index build`, `jn index get`, `jn index check`, `jn index stats`

### Phase 3: Join Integration

**Goal:** Index-backed joins

- [ ] Add `--right-index` flag to `jn-join`
- [ ] Implement indexed join path
- [ ] Implement explicit fallback modes
- [ ] Add `--verify-index` flag
- [ ] Emit query stats events
- [ ] Benchmark vs hash join

**Deliverable:** `jn join --right-index` working with predictable fallback

### Phase 4: Graph Expansion

**Goal:** Multi-hop traversal using lookup indexes

- [ ] Create `tools/zig/jn-graph/` tool
- [ ] Implement `expand` command using lookup indexes
- [ ] Support `--reverse` for incoming edges
- [ ] Support predicate filtering with composite index optimization
- [ ] Enforce `--limit` with truncation event
- [ ] Support seed from stdin
- [ ] Integration tests

**Deliverable:** Working `jn graph expand`

### Phase 5: Incremental Updates

**Goal:** Efficient append-only updates

- [ ] Implement append detection with coverage range
- [ ] Implement delta index build
- [ ] Implement delta-aware query with set freshness
- [ ] Implement `compact` command
- [ ] Handle non-append modifications by category

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
- **Lookup latency**: Time to return first posting offset (excludes source file read and JSON output)

### Lookup Index

| Metric | Target | Measurement |
|--------|--------|-------------|
| Build throughput | >100k records/sec | Single-threaded, SSD |
| Index overhead | 8-30% of source size | Varies with key uniqueness and record size |
| Cold lookup | <10ms | 1M key index, SSD |
| Warm lookup | <0.1ms | 1M key index, cached |
| Query memory | <10MB | Regardless of index size |

**Overhead formula**:
- Per posting: 8 bytes
- Per unique key: 24 bytes + key length
- If 1:1 records to keys with 20-byte keys, overhead ≈ 52 bytes/record

### Graph Expansion

| Metric | Target | Measurement |
|--------|--------|-------------|
| Single hop (out) | <5ms warm | Per node, excludes source I/O |
| 3-hop expansion | <100ms warm | Up to 1000 result nodes |
| Memory | O(visited nodes) | Bounded by `--limit` |

**Memory formula**:
- Visited set: ~40 bytes per node (hash + allocation overhead)
- Frontier: ~40 bytes per pending node
- With `--limit 10000`: ~800KB max

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
- Postings sorted by offset minimize seeks

### Why Lexical Token for Numbers?

- No float rounding errors
- No cross-implementation formatting differences
- "What you type is what you match"
- Simple to implement (capture during parse)

### Why Explicit Fallback Modes?

Users choose `--right-index` for predictable memory. Silent fallback to hash join violates that contract. Explicit `--fallback hash` lets users opt-in to degraded mode.

### Why Coverage Range Instead of Just Size?

- Enables clean delta semantics (delta starts where base ends)
- Avoids "base is always stale once delta exists" warning spam
- Supports future optimizations (partial indexes, sharding)

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
    ├── index_set.zig     # LookupIndexSet (base + delta)
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
tools/zig/jn-join/main.zig     # Add --right-index, --fallback, --verify-index
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
- **Explicit behavior**: Fallback modes and staleness categories are explicit
- **Composable**: Integrates with existing pipeline tools

Key implementation choices:
- Binary format with coverage range, tail hash, and CRC32 checksums
- xxh3_64 hashing with sorted key table
- Lexical token encoding for numbers
- Canonical JSON array for composite keys
- Inode + size + mtime_ns + coverage + tail hash for staleness
- Staleness categories with safe (append-verified) vs unsafe distinction
- Structural validation on open; full CRC opt-in
- LookupIndexSet abstraction for delta-aware consumers
- Graph traversal via lookup indexes with `--limit` enforcement
- Single-delta policy for incremental updates with set-level freshness
