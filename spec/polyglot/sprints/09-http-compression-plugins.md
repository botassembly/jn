# Sprint 09: HTTP & Compression Plugins

**Status:** 🚧 PARTIAL (GZ Zig complete, HTTP remains Python)

**Goal:** Build HTTP protocol and GZ compression plugins in Zig

**Prerequisite:** Sprint 08 complete (integration & production ready)

---

## Deliverables

1. ✅ GZ compression plugin (Zig) - decompression only
2. ⏸️ HTTP protocol plugin (Zig) - deferred, Python works well
3. ✅ Integration with existing pipeline

---

## Phase 1: GZ Compression Plugin

### Core Implementation
- [x] Create `plugins/zig/gz/` directory
- [x] Use Zig std.compress.flate with gzip container
- [x] Implement streaming decompression (raw mode)
- [ ] ~~Implement streaming compression (write mode)~~ - Deferred (Zig std.compress incomplete)

### Read Mode (raw)
```bash
cat file.json.gz | jn-gz --mode=raw | jn filter '.x > 10'
```

- [x] Stream decompress to stdout
- [x] Handle partial reads (streaming)
- [x] SIGPIPE handling (exit cleanly on downstream close)

### Write Mode
**Status:** Deferred - Zig std.compress.flate.Compress has incomplete implementation (@panic("TODO")).
Python gz_.py continues to handle write mode via fallback.

### Quality Gate
- [x] Decompression works correctly
- [x] Streaming (constant memory with 64KB buffers)
- [x] Integration with pipeline: `jn cat file.csv.gz` works

---

## Phase 2: HTTP Protocol Plugin

**Status:** ⏸️ DEFERRED - Python implementation is working well

### Rationale for Deferral
The Python HTTP plugin (http_.py) provides:
- Full HTTP/HTTPS support via `requests` library
- Profile integration with hierarchical config
- Environment variable substitution
- Streaming response handling
- All 6 HTTP tests passing

Implementing in Zig would require:
- TLS/SSL support (complex - needs OpenSSL or similar)
- Profile system reimplementation (currently Python)
- Significant effort with minimal performance benefit for typical API calls

### Current Status (Python)
```bash
jn cat http://api.example.com/data.json | jn filter '.active'
```

- [x] Parse URL (Python)
- [x] Make HTTP request (Python requests)
- [x] Stream response body to stdout
- [x] Handle redirects
- [x] HTTPS support
- [x] Custom headers
- [x] Profile integration

### Future Considerations
If Zig HTTP is pursued in the future:
- [ ] Wait for Zig std.http to mature
- [ ] Consider libcurl via @cImport for TLS
- [ ] Profile system needs Python interop

---

## Phase 3: Profile Integration

**Status:** ✅ COMPLETE (via Python http_.py)

### HTTP Profiles
```
$JN_HOME/profiles/http/myapi/_meta.json
```

- [x] Read base URL from profile
- [x] Read default headers from profile
- [x] Read auth configuration from profile

### Usage
```bash
# Without profile
jn cat "http://api.example.com/users" --header="X-API-Key:xxx"

# With profile
jn cat "@myapi/users"  # Uses profile for base URL + auth
```

### Implementation (Python)
- [x] Check for matching profile before request
- [x] Merge profile config with CLI options
- [x] CLI options override profile
- [x] Environment variable substitution (${VAR})

---

## Phase 4: Pipeline Integration

**Status:** ✅ COMPLETE

### Compression in Pipeline
```bash
# Auto-detect .gz extension - works!
jn cat data.csv.gz | jn filter '.x > 10' | jn put out.json
```

- [x] Discovery recognizes .gz extension
- [x] Chain: gz (Zig) decompress → format read
- [ ] Chain: format write → gz compress (uses Python fallback)

### HTTP in Pipeline
```bash
jn cat http://api.com/data.json | jn filter '.active' | jn put out.csv
```

- [x] Discovery recognizes http:// protocol (Python)
- [x] Response streaming to next stage
- [x] Error propagation

### Quality Gate
- [x] `jn cat file.csv.gz` works (Zig gz + Zig csv)
- [x] `jn cat http://api/data.json` works (Python HTTP + Zig JSON)
- [x] Mixed pipelines work correctly

---

## Phase 5: Testing

**Status:** ✅ All tests passing

### GZ Tests (Zig - decompression only)
| Test | Read (Zig) | Write (Python fallback) |
|------|------------|-------------------------|
| Small file | ✅ | ✅ (Python) |
| Streaming | ✅ | ✅ (Python) |
| Pipeline integration | ✅ | N/A |

### HTTP Tests (Python)
| Test | Status |
|------|--------|
| GET request | ✅ |
| JSON array response | ✅ |
| Custom headers | ✅ |
| 404 error handling | ✅ |
| jn cat HTTP | ✅ |
| jn run HTTP to CSV | ✅ |

### Integration Tests
- [x] `jn cat file.csv.gz` - Zig gz → Zig csv
- [x] HTTP tests with local mock server
- [x] 7 tests passing (1 GZ + 6 HTTP)

---

## Phase 6: Performance

### GZ Benchmarks (Zig)
| Operation | Status | Notes |
|-----------|--------|-------|
| Decompress | ✅ | Uses std.compress.flate, streaming |
| Memory | ✅ | 64KB buffers + 64KB window (constant) |

### HTTP Performance (Python)
| Metric | Status | Notes |
|--------|--------|-------|
| Streaming | ✅ | Uses requests library |
| Memory | ✅ | Streaming mode |

### Binary Size
- [x] GZ plugin: ~150KB (ReleaseFast)
- [ ] HTTP plugin: N/A (uses Python)

---

## Success Criteria

| Plugin | Read | Write | Tests | Implementation |
|--------|------|-------|-------|----------------|
| GZ | ✅ | ⏸️ | Pass | Zig (decompress) |
| HTTP | ✅ | N/A | Pass | Python (mature) |

---

## Notes

**What was implemented:**
- GZ decompression in Zig using std.compress.flate with gzip container
- Streaming I/O with 64KB buffers
- SIGPIPE handling for pipeline early termination

**What was deferred:**
- GZ compression (Zig std.compress.Compress incomplete - @panic("TODO"))
- HTTP in Zig (TLS complexity, Python works well)

**Key learnings:**
- Zig 0.15.2 std.io API significantly different from earlier versions
- File.stdout().writer(&buf) for buffered output
- std.compress.flate works for decompression, compression incomplete
- Python fallback strategy allows incremental Zig migration

**Next steps:**
- Monitor Zig std library development for compression fixes
- Consider Zig HTTP when std.http matures with TLS support
- Other compression formats (zstd) when needed
