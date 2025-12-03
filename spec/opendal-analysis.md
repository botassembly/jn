# OpenDAL Integration Analysis

## What is OpenDAL?

[Apache OpenDAL](https://github.com/apache/opendal) ("One Layer, All Storage") is a unified data access layer that abstracts 70+ storage backends through a consistent API. It graduated from Apache Incubator and is production-ready.

### Supported Services (59+ backends)

| Category | Services |
|----------|----------|
| **Object Storage** | s3, gcs, azblob, oss, cos, obs, b2, swift |
| **File Systems** | fs, hdfs, hdfs-native, webhdfs, azdls, azfile, alluxio |
| **Protocols** | http, ftp, sftp, webdav, ipfs |
| **Consumer Cloud** | gdrive, onedrive, dropbox, pcloud, seafile, yandex-disk |
| **Key-Value** | redis, rocksdb, etcd, memcached, tikv, foundationdb |
| **Databases** | mongodb, postgresql, mysql, sqlite, surrealdb |
| **Cache** | memory, moka, ghac |

### Zig Binding Status

- **Status:** Work-in-progress (unreleased)
- **Requires:** Zig 0.14.0+ (we're on 0.15.2 ✓)
- **API:** Operator-based (init with scheme, call operations)

```zig
// Example usage
var op = try Operator.init("s3", config);
defer op.deinit();

const data = try op.read("path/to/file.csv");
try op.write("output/file.json", output_data);
```

**Operations available:**
- `read(path)` → bytes
- `write(path, data)`
- `delete(path)`
- `copy(src, dst)`
- `rename(src, dst)`
- `stat(path)` → Metadata
- `exists(path)` → bool
- `list(path)` → Lister (iterator)
- `createDir(path)`

---

## How It Fits JN Architecture

### Current Plan (Without OpenDAL)

```
jn cat s3://bucket/data.csv | jn filter '.x > 10' | jn put output.json

┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  s3     │────▶│   csv   │────▶│   zq    │────▶│  json   │
│ plugin  │     │ plugin  │     │ filter  │     │ plugin  │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
```

We'd need to build:
- HTTP plugin (Phase 6)
- S3 plugin (future)
- HDFS plugin (future)
- GCS plugin (future)
- FTP/SFTP plugins (future)
- etc.

### With OpenDAL

```
jn cat s3://bucket/data.csv | jn filter '.x > 10' | jn put output.json

┌─────────────────────┐     ┌─────────┐     ┌─────────┐
│   OpenDAL unified   │────▶│   csv   │────▶│  json   │
│   (s3, http, hdfs,  │     │ plugin  │     │ plugin  │
│    gcs, ftp, etc.)  │     │         │     │         │
└─────────────────────┘     └─────────┘     └─────────┘
```

**One protocol plugin handles ALL storage backends.**

---

## URI/Matches/Resolution Design

### Scheme-Based Routing

OpenDAL uses scheme strings to select backends:

| JN Address | OpenDAL Scheme | Notes |
|------------|----------------|-------|
| `s3://bucket/path` | `s3` | AWS S3 |
| `gs://bucket/path` | `gcs` | Google Cloud Storage |
| `az://container/path` | `azblob` | Azure Blob |
| `hdfs://namenode/path` | `hdfs` | Hadoop |
| `http://example.com/data` | `http` | HTTP(S) |
| `ftp://server/path` | `ftp` | FTP |
| `sftp://server/path` | `sftp` | SFTP |
| `file:///local/path` | `fs` | Local filesystem |
| `redis://host/key` | `redis` | Redis |
| `webdav://server/path` | `webdav` | WebDAV |

### Plugin Matches Pattern

```toml
# Single OpenDAL plugin handles all remote protocols
[tool.jn]
matches = [
    "^s3://",
    "^gs://",
    "^gcs://",
    "^az://",
    "^azblob://",
    "^hdfs://",
    "^webhdfs://",
    "^http://",
    "^https://",
    "^ftp://",
    "^sftp://",
    "^webdav://",
    "^redis://",
    "^ipfs://",
    # ... all 59+ schemes
]
role = "protocol"
modes = ["read", "raw"]
```

### Resolution Logic

```
Address: s3://my-bucket/data/sales.csv.gz

1. Parse address
   ├── Protocol: s3
   ├── Path: my-bucket/data/sales.csv.gz
   └── Compression: .gz detected

2. Route to OpenDAL plugin
   └── scheme = "s3"

3. OpenDAL reads bytes
   └── Operator.init("s3", bucket_config).read(path)

4. Chain decompression + format
   └── gz --mode=raw | csv --mode=read
```

---

## What Changes in the Plan

### Phases That Get REPLACED

| Phase | Original | With OpenDAL |
|-------|----------|--------------|
| **6** | HTTP Protocol (Zig HTTP plugin) | **ELIMINATED** - OpenDAL handles HTTP |
| **Future** | S3 plugin | **ELIMINATED** |
| **Future** | HDFS plugin | **ELIMINATED** |
| **Future** | GCS plugin | **ELIMINATED** |
| **Future** | FTP/SFTP plugins | **ELIMINATED** |

### Phases That Get SIMPLIFIED

| Phase | Change |
|-------|--------|
| **3** | Address parser recognizes OpenDAL schemes |
| **4** | jn-cat delegates to OpenDAL for remote sources |
| **5** | Discovery just needs one OpenDAL plugin |

### New Phase: OpenDAL Integration

```
Phase 1.5: OpenDAL Foundation
├── Build opendal-c library
├── Create Zig binding wrapper
├── Create opendal plugin (plugins/zig/opendal/)
├── Implement scheme → config mapping
└── Profile integration for credentials
```

---

## Profile Integration

### How Credentials Work

OpenDAL requires configuration per-service:

```zig
// S3 example
var config = std.StringHashMap([]const u8).init(allocator);
try config.put("bucket", "my-bucket");
try config.put("region", "us-east-1");
try config.put("access_key_id", "${AWS_ACCESS_KEY_ID}");
try config.put("secret_access_key", "${AWS_SECRET_ACCESS_KEY}");

var op = try Operator.init("s3", config);
```

### JN Profile Mapping

```
$JN_HOME/profiles/opendal/
├── s3/
│   └── my-bucket/
│       └── _meta.json    # bucket, region, access_key_id, secret_access_key
├── hdfs/
│   └── cluster/
│       └── _meta.json    # namenode, user
└── gcs/
    └── my-project/
        └── _meta.json    # project_id, credentials_path
```

Usage:
```bash
jn cat @s3/my-bucket/data.csv      # Uses profile for credentials
jn cat s3://bucket/path            # Uses env vars or default credentials
```

---

## What We KEEP Building

Even with OpenDAL, we still need:

| Component | Why |
|-----------|-----|
| **Format plugins** (csv, json, yaml) | OpenDAL returns raw bytes |
| **Compression plugins** (gz, bz2) | OpenDAL doesn't decompress |
| **ZQ filter engine** | Transformation layer |
| **CLI tools** (jn-cat, jn-put, etc.) | Orchestration |
| **Profile system** | Credential management |
| **Plugin discovery** | Find plugins |
| **Python plugins** | xlsx, gmail, mcp, duckdb |

---

## Risk Assessment

### Concerns

| Risk | Severity | Mitigation |
|------|----------|------------|
| Zig binding WIP | Medium | Prototype first, fallback to C binding directly |
| C library dependency | Low | Build as part of `make install` |
| API stability | Medium | Pin to specific version |
| Missing schemes | Low | 70+ services, covers most needs |
| Streaming support | ~~High~~ **Resolved** | ✅ Confirmed - C API has streaming reader/writer |

### Critical Question: Streaming ✅ CONFIRMED

JN's architecture relies on streaming. **OpenDAL supports it:**

**C API (which Zig wraps):**
```c
// Streaming reader API
opendal_reader* reader = opendal_operator_reader(op, path);
opendal_reader_read(reader, buffer, len);  // Read chunks
opendal_reader_seek(reader, offset);       // Seek support
opendal_reader_free(reader);

// Streaming writer API
opendal_writer* writer = opendal_operator_writer(op, path);
opendal_writer_write(writer, data, len);   // Write chunks
opendal_writer_close(writer);              // Finalize
```

**Rust API (for reference):**
```rust
// Zero-copy streaming
let reader = op.reader("huge-file.csv").await?;
let stream = reader.into_bytes_stream(0..);  // Stream of Bytes
```

**Key points:**
- Blocking API (perfect for JN's process model)
- Chunk-based reading (constant memory)
- Seek support for range requests
- Zero-copy design in Rust core

**Verdict: OpenDAL is architecturally compatible with JN.**

---

## Prototype Plan

### Phase 1: Verify Streaming (1-2 days)

```bash
# Build OpenDAL C library
cd /tmp && git clone https://github.com/apache/opendal
cd opendal/bindings/c && cargo build --release

# Test with Zig
zig build libopendal_c
```

Write test:
```zig
// Test: Can we stream read a large file?
var op = try Operator.init("fs", null);
// Check if there's a streaming API vs buffered read
```

### Phase 2: Prototype Plugin (2-3 days)

```
plugins/zig/opendal/
├── main.zig           # Plugin entry point
├── schemes.zig        # Scheme → config mapping
└── build.zig          # Links opendal-c
```

Test with:
```bash
# Local filesystem (easiest)
echo '{"x":1}' > /tmp/test.json
plugins/zig/opendal/bin/opendal --mode=raw --scheme=fs --path=/tmp/test.json

# HTTP
plugins/zig/opendal/bin/opendal --mode=raw --scheme=http --url=https://example.com/data.json

# S3 (if credentials available)
plugins/zig/opendal/bin/opendal --mode=raw --scheme=s3 --bucket=test --path=data.csv
```

### Phase 3: Integration Test (1 day)

```bash
# Full pipeline through OpenDAL
jn cat s3://bucket/data.csv.gz | jn filter '.x > 10' | jn put output.json
```

---

## Recommendation

### Do This First

1. **Clone OpenDAL and inspect Zig binding code** - Verify streaming capability
2. **Build the C library locally** - Ensure it compiles
3. **Write minimal Zig test** - Read local file, check memory usage

### Decision Point

After prototype:

| Result | Action |
|--------|--------|
| **Streaming works** | Adopt OpenDAL, revise plan |
| **Buffering only** | Skip OpenDAL for data, maybe use for metadata |
| **Build fails** | Fallback to custom HTTP plugin |

### If Successful

Revised timeline:
- **-2 weeks** from original plan (no HTTP/S3/HDFS plugins)
- **+1 week** for OpenDAL integration
- **Net: 1 week faster** + future protocols "free"

---

## Summary

| Aspect | Assessment |
|--------|------------|
| **Potential value** | Very high - 70+ backends for free |
| **Risk** | Medium - WIP binding, streaming unknown |
| **Effort to prototype** | Low - 3-5 days |
| **Recommendation** | **Prototype before committing** |

Sources:
- [Apache OpenDAL GitHub](https://github.com/apache/opendal)
- [OpenDAL Zig Bindings](https://github.com/apache/opendal/tree/main/bindings/zig)
- [OpenDAL Services Documentation](https://opendal.apache.org/docs/rust/opendal/services/index.html)
