# Sprint 09: HTTP & Compression Plugins

**Status:** 🔲 PLANNED

**Goal:** Build HTTP protocol and GZ compression plugins in Zig

**Prerequisite:** Sprint 08 complete (integration & production ready)

---

## Deliverables

1. HTTP protocol plugin (Zig)
2. GZ compression plugin (Zig)
3. Integration with existing pipeline

---

## Phase 1: GZ Compression Plugin

### Core Implementation
- [ ] Create `plugins/zig/gz/` directory
- [ ] Use zlib via @cImport or Zig std.compress
- [ ] Implement streaming decompression (read mode)
- [ ] Implement streaming compression (write mode)

### Read Mode
```bash
cat file.json.gz | jn-gz --mode=read | jn filter '.x > 10'
```

- [ ] Detect gzip magic bytes
- [ ] Stream decompress to stdout
- [ ] Handle partial reads (streaming)

### Write Mode
```bash
jn cat data.csv | jn-gz --mode=write > data.ndjson.gz
```

- [ ] Stream compress from stdin
- [ ] Configurable compression level (1-9)

### Options
- [ ] `--level=6` - compression level (default 6)
- [ ] Auto-detect on read (magic bytes)

### Quality Gate
- [ ] 1GB compressed file decompresses correctly
- [ ] Round-trip preserves data
- [ ] Streaming (constant memory)

---

## Phase 2: HTTP Protocol Plugin

### Core Implementation
- [ ] Create `plugins/zig/http/` directory
- [ ] Use std.http.Client or @cImport libcurl
- [ ] Support GET/POST methods
- [ ] Handle HTTP/HTTPS

### Read Mode
```bash
jn cat http://api.example.com/data.json | jn filter '.active'
```

- [ ] Parse URL
- [ ] Make HTTP request
- [ ] Stream response body to stdout
- [ ] Handle redirects (configurable limit)

### Options
- [ ] `--method=GET` - HTTP method
- [ ] `--header=X-API-Key:xxx` - custom headers (repeatable)
- [ ] `--timeout=30` - request timeout in seconds
- [ ] `--follow-redirects` - follow redirects (default true)
- [ ] `--max-redirects=5` - redirect limit

### Authentication
- [ ] Basic auth via URL: `http://user:pass@host/path`
- [ ] Bearer token via header: `--header=Authorization:Bearer xxx`
- [ ] Profile integration for credentials

### Error Handling
- [ ] Non-2xx status → stderr error, exit 1
- [ ] Timeout → stderr error, exit 1
- [ ] Connection refused → clear error message

### Quality Gate
- [ ] GET request works
- [ ] HTTPS works
- [ ] Headers passed correctly
- [ ] Streaming large responses (>100MB)

---

## Phase 3: Profile Integration

### HTTP Profiles
```
$JN_HOME/profiles/http/myapi/_meta.json
```

- [ ] Read base URL from profile
- [ ] Read default headers from profile
- [ ] Read auth configuration from profile

### Usage
```bash
# Without profile
jn cat "http://api.example.com/users" --header="X-API-Key:xxx"

# With profile
jn cat "http://myapi/users"  # Uses profile for base URL + auth
```

### Implementation
- [ ] Check for matching profile before request
- [ ] Merge profile config with CLI options
- [ ] CLI options override profile

### Quality Gate
- [ ] Profile-based requests work
- [ ] CLI options override profile
- [ ] Clear error if profile not found

---

## Phase 4: Pipeline Integration

### Compression in Pipeline
```bash
# Auto-detect .gz extension
jn cat data.csv.gz | jn filter '.x > 10' | jn put out.json

# Explicit compression
jn cat data.csv | jn put out.json.gz
```

- [ ] Discovery recognizes .gz extension
- [ ] Chain: gz decompress → format read
- [ ] Chain: format write → gz compress

### HTTP in Pipeline
```bash
jn cat http://api.com/data.json | jn filter '.active' | jn put out.csv
```

- [ ] Discovery recognizes http:// protocol
- [ ] Response streaming to next stage
- [ ] Error propagation

### Quality Gate
- [ ] `jn cat file.csv.gz` works (auto decompress + CSV parse)
- [ ] `jn cat http://api/data.json` works (HTTP + JSON parse)
- [ ] Mixed pipelines work correctly

---

## Phase 5: Testing

### GZ Tests
| Test | Read | Write |
|------|------|-------|
| Small file | ✅ | ✅ |
| Large file (1GB) | ✅ | ✅ |
| Corrupted gzip | ✅ | N/A |
| Streaming | ✅ | ✅ |
| All compression levels | N/A | ✅ |

### HTTP Tests
| Test | Status |
|------|--------|
| GET request | ✅ |
| POST request | ✅ |
| Custom headers | ✅ |
| Basic auth | ✅ |
| HTTPS | ✅ |
| Redirects | ✅ |
| Timeout | ✅ |
| Large response | ✅ |
| Error handling | ✅ |

### Integration Tests
- [ ] `jn cat file.csv.gz | jn filter '.x > 10' | jn put out.json`
- [ ] `jn cat http://httpbin.org/json | jn put out.csv`
- [ ] Profile-based HTTP requests

### Quality Gate
- [ ] All tests pass
- [ ] Performance meets targets

---

## Phase 6: Performance

### GZ Benchmarks
| Operation | File Size | Target | vs Python |
|-----------|-----------|--------|-----------|
| Decompress | 1GB | <10s | 3x faster |
| Compress | 1GB | <30s | 3x faster |

### HTTP Benchmarks
| Metric | Target |
|--------|--------|
| Time to first byte | <100ms (local) |
| Throughput | >100MB/s |
| Memory | Constant (streaming) |

### Binary Size
- [ ] GZ plugin <200KB (ReleaseSmall)
- [ ] HTTP plugin <500KB (ReleaseSmall)

### Quality Gate
- [ ] All benchmarks meet targets
- [ ] Memory constant during streaming

---

## Success Criteria

| Plugin | Read | Write | Tests | Performance |
|--------|------|-------|-------|-------------|
| GZ | ✅ | ✅ | Pass | 3x faster |
| HTTP | ✅ | N/A | Pass | Streaming |

---

## Notes

**Library Options:**
- GZ: std.compress.gzip or zlib via @cImport
- HTTP: std.http or libcurl via @cImport

**Deferred:**
- Write mode for HTTP (POST body from stdin)
- Other compression formats (bz2, xz, zstd)
- WebSocket protocol

**Dependencies:**
- May need to bundle or link against system zlib
- HTTPS requires TLS (std.crypto or OpenSSL via @cImport)
