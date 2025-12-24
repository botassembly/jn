# JN Indexes

> **Purpose**: Make NDJSON act like a fast, local "lookup substrate" for agents—without turning JN into a database.

---

## The Problem

JN is optimized for streaming transformation, but agents routinely hit three classes of operations where streaming alone is not enough:

1) **Keyed lookups**
   - "Given `customer_id`, fetch customer record"
   - "Given `code`, fetch concept"
   - Current options:
     - scan the file (slow)
     - hash-join by loading the whole right side (fast but memory-heavy)

2) **Multi-hop traversals (graph expansion)**
   - "Start from a concept, follow `subClassOf` 3 hops"
   - "Expand synonyms → broader terms → mapped codes"
   - Current option:
     - repeatedly scan `edges.jsonl` or re-materialize in-memory maps

3) **Repeated joins**
   - Agents frequently run the same join shape many times in pipelines.
   - Rebuilding an in-memory hash table every run is wasteful.

Agents need **sub-second** and often **sub-100ms** response for these "navigation and enrichment" steps, while keeping JN's core properties:
- predictable memory
- composable CLI tools
- NDJSON everywhere as the interchange

---

## The Solution: Derived Access Paths for NDJSON

JN Indexes introduce a single concept:

> **An index is a derived artifact that makes NDJSON queryable by key without scanning.**

The source of truth remains the NDJSON file(s). The index is disposable, rebuildable, and always verifiable.

### What changes for the user

- You keep your files as NDJSON (`nodes.jsonl`, `edges.jsonl`, lookup tables, etc.)
- You run `jn index build ...` once (or periodically)
- Now JN tools can do:
  - **O(1)-ish lookups** by key (mmapped index, tiny working set)
  - **disk-backed joins** with bounded memory
  - **fast adjacency** for graph expansion (neighbors per node without scanning)

---

## Core Insight

Most "agent ETL navigation" workloads reduce to:

- **Equality lookups** (key → record(s))
- **Adjacency** (node → neighbors)
- **Repeated application** of the above (multi-hop expansion, join chains)

You do not need a general query engine to make those fast. You need:
- a compact key index
- a postings list of matches (record offsets and/or projections)
- an execution model that **streams results** back out as NDJSON

---

## Core Philosophy

### 1) NDJSON remains canonical
- **The data is still NDJSON.**
- The index does not own data; it only points to it or stores small projections.
- You can delete the index and rebuild it at any time.

This preserves JN's simplicity: "inspect with `head`, debug with `jq`, glue with pipes."

### 2) Indexes are accelerators, not databases
JN Indexes are explicitly **not**:
- a transactional store
- a multi-user concurrent DB
- a general query language runtime
- a document management system

They are **precomputed access paths** optimized for the 80/20 of agent lookups and expansions.

### 3) Streaming output always
Even though lookups are random-access internally, indexed commands:
- emit NDJSON line-by-line
- do not accumulate full result sets unless asked
- preserve backpressure and composability

### 4) Disk-first, mmap-first
Indexes are structured so they can be:
- memory-mapped
- queried with tiny working sets
- accelerated by the OS page cache

This aligns with JN's "predictable resources" story: **RAM proportional to hot pages, not dataset size**.

### 5) Correctness over cleverness
- Index build is atomic (write new artifact, then swap)
- Index usage is guarded (staleness detection)
- Index can be validated (`jn index check`)
- Fallback behavior (scan/hash) is **explicit and opt-in** and always emits a JSONL event to stderr

Agents should never silently use an incorrect index.

---

## What JN Indexes Enable

### A) Fast lookup: `key → record(s)`
Use case: dimension table enrichment, code lookup, mapping table.

- Build:
  ```bash
  jn index build customers.jsonl --on customer_id
  ```
- Query:
  ```bash
  jn index get customers.jsonl --key customer_id --eq C123
  ```
- Output: matching records as NDJSON to stdout.

### B) Disk-backed join: stream left, index right
Use case: join when right side is too large to hash into RAM, or when the join repeats frequently.

- Build right-side index once:
  ```bash
  jn index build customers.jsonl --on customer_id
  ```
- Join:
  ```bash
  jn cat orders.jsonl | jn join customers.jsonl --on customer_id --right-index
  ```

**Semantics stay the same as `jn join` today**; only the right-side access path changes.

### C) Graph expansion: adjacency without scanning edges.jsonl
Use case: taxonomy/ontology expansion, relationship walking.

- Canonical files:
  - `nodes.jsonl` (optional for labels/metadata)
  - `edges.jsonl` with `{from, pred, to, props}`

- Build adjacency access paths (v1 uses ordinary lookup indexes):
  ```bash
  # Outgoing adjacency
  jn index build edges.jsonl --on from

  # Incoming adjacency (reverse traversal)
  jn index build edges.jsonl --on to

  # Optional accelerator for predicate-specific traversal
  jn index build edges.jsonl --on "from,pred"
  ```

- Expand:
  ```bash
  jn graph expand edges.jsonl --seed "C123" --pred subClassOf --hops 3
  ```

The key: expansion hits **indexes**, not the raw JSONL file.

---

## Design Principle: Minimal cognitive load

The indexing feature only works if it feels like a "small, obvious Unix tool," not a subsystem.

### The user model should be:
1) "I have NDJSON."
2) "I can optionally build an index to speed up lookups."
3) "JN tools will use it when it exists."

### A minimal CLI surface (v1)
- `jn index build <file> --on <field[,field...]> [--mode unique|multi]`
- `jn index get <file> --key <field> --eq <value>`
- `jn index check <file> --key <field>`
- `jn index stats <file> --key <field>`
- `jn index update <file> --key <field>` (optional; append-only)
- `jn index compact <file> --key <field>` (optional; delta merge)
- `jn graph expand <edges.jsonl> ...` (uses the lookup indexes above)

Everything else is sugar built on top.

---

## Index Kinds (only what you need)

### 1) Lookup index (for joins and keyed get)
Maps:
- `key -> file offsets of matching records` (or a unique offset)

This supports:
- `jn index get`
- `jn join --right-index`

### 2) Adjacency via lookup indexes (for traversals)
Graph adjacency is expressed as lookup indexes on edge fields:
- `from -> edges`
- optionally `to -> edges`
- optionally `(from,pred) -> edges` for predicate-restricted traversal

This supports:
- `out(node)`
- `in(node)`
- `expand(seed, hops, pred-filter)`

### 3) Select-property indexing (optional, but very powerful)
To seed expansions quickly, selected node properties can be represented as **synthetic edges**, then indexed like any other edge file.

Example: index `code`, `synonyms[]`, `label`:
- `(node, @code, "E11")`
- `(node, @syn, "t2dm")`

Then "find by code/synonym" becomes a reverse adjacency lookup (index `to`), and expansion continues over the same edge model.

---

## Incremental updates: "fast when append-only, honest otherwise"

JN is CLI-first and daemon-free. Index maintenance must match that reality.

### Mode 1: Append-friendly (recommended)
If a file grows by appending new NDJSON lines:
- `jn index update` ingests only the new suffix
- writes a small delta index
- queries consult base + delta
- `jn index compact` merges segments later

### Mode 2: Mutable files (fallback)
If the file is edited in-place:
- index detects "non-append modification"
- requires a full rebuild (`jn index build --full`)
- tools do not silently use unsafe indexes

---

## How this fits JN's identity (and doesn't violate it)

JN still doesn't *become* a database. It produces **derived local artifacts** that accelerate streaming pipelines.

The canonical data remains:
- your NDJSON files
- your existing toolchain (`jn cat`, `jn filter`, `zq`, etc.)

Indexes are opt-in accelerators that are:
- local
- rebuildable
- visible (stats/check)
- not a new storage system users must learn

---

## Agent-first ergonomics

### Deterministic, structured behavior
- stdout: NDJSON records/bindings
- stderr: JSONL events:
  - build stats
  - staleness detection
  - explicit fallback notices (if enabled)
  - query stats (optional)
  - explain plans (optional)

### Explainability
Add `--explain` to show how a join/traversal was executed:
- used index vs scan/hash
- index freshness
- rows touched (approx)
- latency stats

Agents can use this to decide whether to rebuild/compact.

---

## Success Criteria

JN Indexes succeed when:

1) **Lookups are instant-feeling**
   - "get by key" returns first output in <10ms on warm cache for typical indices.

2) **Joins stop being memory-bound**
   - join can enrich a large stream using a large right-side file without loading it into RAM.

3) **Graph expansion is fast and predictable**
   - multi-hop expansions over `edges.jsonl` run sub-second for common taxonomy workloads.

4) **The mental model stays small**
   - users learn one new concept: `jn index build`
   - everything else "just uses it."

5) **Correctness is never ambiguous**
   - staleness detection is reliable
   - rebuild is easy and atomic
   - failure modes are explicit and machine-readable

---

## Non-Goals

To keep the feature focused:

- No general-purpose query engine (no SPARQL, no SQL)
- No full-text search (leave that to dedicated tools)
- No distributed indexing
- No transactional semantics
- No hidden background processes required

---

## One-line positioning

**JN Indexes make NDJSON behave like a fast local lookup substrate for agents—while keeping JN streaming, composable, and simple.**
