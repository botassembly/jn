# Zig Libraries Evaluation for JN Refactor

**Date:** 2024-12-03

This document evaluates external Zig/C libraries that could accelerate the JN Zig refactor.

---

## Executive Summary

| Library | Verdict | Rationale |
|---------|---------|-----------|
| **OpenDAL** | ✅ ADOPT | Prototype verified - 70+ storage backends via single plugin |
| **zuckdb.zig** | ⏸️ DEFER | Keep DuckDB in Python for now - complex C++ dependency |
| **arrow-zig** | ⏸️ DEFER | No Parquet support; Arrow IPC less common in JN workflows |
| **ctregex.zig** | ⚠️ CONSIDER | Useful for address matching; incomplete feature set |
| **CSV libraries** | ❌ SKIP | Already have working custom implementation |
| **XML libraries** | ⏸️ DEFER | Low priority - can add later if needed |
| **YAML libraries** | ⏸️ DEFER | Profile configs are JSON; YAML parsing is future need |
| **prettytable-zig** | ❌ SKIP | Table rendering not required for core Zig tools |

---

## Detailed Evaluations

### 1. OpenDAL (Apache) ✅ ADOPT

**Repository:** https://github.com/apache/opendal

**What it does:** Unified data access layer for 70+ storage backends (S3, HDFS, GCS, HTTP, FTP, SFTP, etc.)

**Prototype Status:** ✅ VERIFIED WORKING
- Zig 0.15.2 links to C library successfully
- Streaming reads work (chunked, constant memory)
- Memory, filesystem backends tested
- HTTP backend initializes (network access needed for full test)

**Why adopt:**
- Eliminates Phase 6 (HTTP plugin) from plan
- Eliminates future S3/HDFS/GCS/FTP plugin work
- Single plugin handles all remote protocols
- Apache-graduated, production-ready

**Integration path:**
1. Build opendal-c library as part of `make install`
2. Create `plugins/zig/opendal/` plugin with scheme routing
3. Map JN profiles to OpenDAL operator configs

**See:** `spec/opendal-analysis.md` for full details.

---

### 2. zuckdb.zig (DuckDB) ⏸️ DEFER

**Repository:** https://github.com/karlseguin/zuckdb.zig

**What it does:** Zig bindings for DuckDB analytical database.

**Features:**
- Connection pooling (thread-safe)
- Prepared statements
- Comprehensive type support (i8-i128, strings, dates, UUIDs, enums, lists)
- Tested with DuckDB 1.3.2

**Why defer:**
1. **DuckDB is C++** - Large dependency (~50MB), complex build
2. **Current Python plugin works well** - Low startup overhead acceptable for DB queries
3. **Profile system complexity** - SQL templates, parameter injection already working in Python
4. **Limited upside** - Query execution time dominates; startup time less important

**Future consideration:**
If DuckDB becomes a hot path (many small queries), revisit Zig bindings.

---

### 3. arrow-zig ⏸️ DEFER

**Repository:** https://github.com/clickingbuttons/arrow-zig

**What it does:** Apache Arrow array construction and IPC serialization in Zig.

**Features:**
- 11 Arrow array types mapped to Zig
- Zero-copy FFI support
- Arrow IPC (streaming and file formats)

**Limitations:**
- **No Parquet support** - Major gap for data workflows
- No Decimal type
- Complex schemas may have interoperability issues

**Why defer:**
1. **Parquet is the common format** - Arrow IPC is less common in JN use cases
2. **No Parquet means limited value** - Would need separate Parquet library anyway
3. **DuckDB handles Parquet well** - Current Python plugin reads/writes Parquet via DuckDB

**Future consideration:**
If high-performance Arrow processing becomes needed, revisit. Consider pairing with a Parquet library.

---

### 4. ctregex.zig ⚠️ CONSIDER

**Repository:** https://github.com/alexnask/ctregex.zig

**What it does:** Compile-time regex compilation with runtime matching.

**Features:**
- Comptime regex → optimized code
- UTF-8, UTF-16, ASCII support
- Named capture groups
- Standard quantifiers and character classes

**Limitations:**
- No DFA generation (slower than production regex engines)
- Missing search/findAll functions
- No backreferences

**Potential uses in JN:**
1. **Address pattern matching** (`^s3://`, `^http://`, file extensions)
2. **Profile reference parsing** (`@namespace/query`)
3. **ZQ expression validation**

**Why consider (not adopt now):**
- Current address matching uses simple string prefix checks
- Performance benefit unclear for JN's patterns (mostly prefix matches)
- Incomplete feature set may require workarounds

**Future path:**
Prototype for address matching in Phase 3 (Address & Profile system).

---

### 5. CSV Libraries ❌ SKIP

**Evaluated:**
- [ZCSV](https://github.com/matthewtolman/zig_csv) - Comprehensive, multiple parser variants
- [zig-csv](https://github.com/DISTREAT/zig-csv) - Low-level, explicit control

**Why skip:**
**JN already has a working CSV plugin** (`plugins/zig/csv/main.zig`):
- Read mode: CSV → NDJSON
- Write mode: NDJSON → CSV
- Configurable delimiter (tab support)
- No-header mode
- Streaming implementation

The existing implementation is:
- Well-tested
- Matches JN's streaming architecture
- Handles TSV via `--delimiter=tab`
- Simple and maintainable (~300 lines)

**Decision:** Keep existing implementation. No external library needed.

---

### 6. XML Libraries ⏸️ DEFER

**Evaluated:**
- [zig-xml](https://github.com/ianprime0509/zig-xml) - Pure Zig, W3C test suite
- [nektro/zig-xml](https://github.com/nektro/zig-xml) - Spec-compliant, UTF-8

**Why defer:**
1. **XML is low priority** for JN's data workflows
2. **Python can handle XML** via lxml when needed
3. **No immediate use case** in current plan phases

**Future consideration:**
Add XML plugin when specific need arises (SOAP APIs, legacy data feeds).

---

### 7. YAML Libraries ⏸️ DEFER

**Evaluated:**
- [zig-yaml](https://github.com/kubkon/zig-yaml) - Work-in-progress YAML 1.2
- [ymlz](https://github.com/pwbh/ymlz) - Struct mapping

**Why defer:**
1. **JN profiles use JSON** (`_meta.json`)
2. **No YAML data format plugin** in current plan
3. **YAML parsing complexity** - Multi-line strings, anchors, etc.

**Future consideration:**
If Kubernetes manifests or other YAML-heavy workflows become common.

---

### 8. prettytable-zig ❌ SKIP

**Repository:** https://github.com/dying-will-bullet/prettytable-zig

**What it does:** ASCII table formatting for terminal output.

**Why skip:**
1. **JN outputs NDJSON** - Not formatted tables
2. **Python CLI handles formatting** - `jn inspect`, `jn head` etc.
3. **VisiData recommended** for visual exploration
4. **Core Zig tools are data pipelines** - Not interactive displays

**Decision:** Table rendering stays in Python layer.

---

### 9. Compression ✅ ALREADY SOLVED

**Current implementation:**
- **Decompression:** `std.compress.flate` (Zig stdlib)
- **Compression:** `comprezz.zig` (~1700 line port of Zig 0.14 deflate)

The gz plugin (`plugins/zig/gz/`) handles:
- `--mode=raw`: Decompress gzip → stdout
- `--mode=write`: Compress stdin → gzip

**No action needed.** Compression is fully working.

---

## Updated Plan Recommendations

### Changes to spec/00-plan.md

1. **Add Phase 1.5: OpenDAL Integration**
   - Build opendal-c library
   - Create opendal plugin with scheme routing
   - Profile integration for credentials

2. **Remove Phase 6: HTTP Protocol**
   - OpenDAL handles HTTP(S)
   - Also handles S3, HDFS, GCS, FTP, SFTP

3. **Keep Python plugins for:**
   - DuckDB (complex dependency, working well)
   - xlsx (openpyxl)
   - Gmail (Google APIs)
   - MCP (async protocol)

### No External Libraries Needed For:

| Component | Approach |
|-----------|----------|
| CSV | Keep existing custom plugin |
| JSON | Keep using std.json |
| JSONL | Keep existing passthrough plugin |
| Compression | Keep comprezz.zig + std.compress.flate |

---

## Library Adoption Timeline

| Phase | Library | Action |
|-------|---------|--------|
| **Now** | OpenDAL | Productionize prototype |
| **Phase 3** | ctregex.zig | Prototype for address matching |
| **Future** | zuckdb.zig | If DuckDB hot path identified |
| **Future** | arrow-zig + parquet | If Arrow/Parquet native support needed |

---

## Appendix: Existing Zig Plugins

| Plugin | Status | Lines | Dependencies |
|--------|--------|-------|--------------|
| `csv` | ✅ Working | ~350 | None |
| `json` | ✅ Working | ~250 | std.json |
| `jsonl` | ✅ Working | ~100 | None |
| `gz` | ✅ Working | ~175 | std.compress.flate + comprezz.zig |
| `opendal` | 🔧 Prototype | ~100 | libopendal_c |

All existing plugins are custom implementations that match JN's streaming architecture. External libraries would add complexity without significant benefit for these use cases.
