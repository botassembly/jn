# HTTP Protocol Plugin - Design

## What

Protocol plugin for fetching data from HTTP/HTTPS endpoints with automatic format detection and streaming support.

## Why

Enable JN to fetch data from web APIs, remote files, and cloud services. Most modern data sources are accessible via HTTP, making this a critical capability for real-world data pipelines.

## Core Architecture

### Plugin Type
**Protocol plugin** - `reads()` only (writes via separate profile system for POST/PUT)

### Pattern Matching
```toml
matches = ["^https?://.*"]
```

Matches any URL starting with `http://` or `https://`

### Key Design Decisions

**1. Automatic Format Detection**
Detect response format via:
- Content-Type header (`application/json`, `text/csv`)
- URL file extension (`.json`, `.csv`)
- Manual override (`--format json`)

**Why:** Users shouldn't specify format twice. If they fetch `data.csv`, assume CSV.

**2. Streaming Architecture**
Process responses line-by-line with constant memory, regardless of size.

**Why:** Enables processing GB-sized responses without buffering entire file. Early termination (`| head -n 10`) stops download immediately.

**3. JSON Array Handling**
JSON arrays yield one NDJSON record per element:
```json
[{"id": 1}, {"id": 2}]  →  {"id": 1}\n{"id": 2}\n
```

**Why:** Consistent with NDJSON philosophy - one record per line enables streaming and piping.

**4. Authentication via Config**
Headers, auth, and API keys passed as arguments or via profiles.

**Why:** Separates concerns - HTTP plugin handles transport, profiles handle credentials.

## Features

- **Methods:** GET, POST, PUT, DELETE
- **Auth:** Bearer tokens, Basic auth, API keys, custom headers
- **Format detection:** JSON, CSV, NDJSON, XML, text
- **Streaming:** Constant memory for large responses
- **Error handling:** HTTP errors, timeouts, SSL failures
- **Profile integration:** `@profile/path` syntax

## Usage Examples

### Basic Fetch
```bash
# Fetch JSON, auto-detect format
jn cat https://opencode.ai/config.json

# Fetch CSV, pipe to filter
jn cat https://example.com/data.csv | jn filter '.revenue > 1000'
```

### With Authentication
```bash
# Bearer token
jn cat https://api.example.com/data \
  --headers '{"Authorization": "Bearer ${API_TOKEN}"}'

# Basic auth
jn cat https://api.example.com/secure --auth "user:pass"
```

### POST Request
```bash
echo '{"query": "test"}' | \
  jn cat https://api.example.com/search --method POST
```

### Profile-Based (see rest-api-profile-design.md)
```bash
# Clean syntax, credentials from profile
jn cat @github/repos/microsoft/vscode/issues
```

## Risks & Challenges

### 1. **Format Detection Ambiguity**
**Risk:** Server returns wrong Content-Type or no extension in URL.

**Mitigation:**
- Fallback: Attempt JSON parse, then treat as text
- Allow `--format` override
- Document common API quirks

### 2. **Memory Exhaustion**
**Risk:** Non-streaming responses (JSON objects) must buffer entire response.

**Mitigation:**
- Document memory implications for large single JSON objects
- Recommend NDJSON for large datasets
- Consider `--max-response-size` flag

### 3. **Authentication Complexity**
**Risk:** OAuth 2.0, JWT refresh, API key rotation not supported initially.

**Mitigation:**
- Phase 1: Basic auth, Bearer tokens, API keys only
- Phase 2: OAuth flow via profiles
- Document workarounds (fetch token separately, use as Bearer)

### 4. **Rate Limiting**
**Risk:** Rapid requests trigger API rate limits, causing 429 errors.

**Mitigation:**
- Phase 1: User handles rate limiting manually
- Phase 2: Profile-based rate limit config
- Document best practices (add delays, respect headers)

### 5. **SSL Certificate Validation**
**Risk:** Self-signed certs or corporate proxies cause SSL errors.

**Mitigation:**
- Default: Verify SSL (secure)
- Flag: `--no-verify-ssl` (with warning)
- Document: When and why to use

### 6. **Large Response Handling**
**Risk:** Downloading 10GB file when user only needs first 100 records.

**Mitigation:**
- Streaming enables early termination
- SIGPIPE propagates shutdown to HTTP connection
- Test: `jn cat huge-file.csv | head -n 10` stops download

### 7. **Binary Content**
**Risk:** Images, PDFs, ZIP files aren't NDJSON-compatible.

**Mitigation:**
- Detect binary content-types
- Yield single record: `{"url": "...", "content_type": "...", "size": 123}`
- Document: Use `--raw` flag or redirect to file

### 8. **Pagination**
**Risk:** APIs return paginated results, need multiple requests.

**Mitigation:**
- Phase 1: Manual pagination (user loops)
- Phase 2: Profile-based pagination config
- Document patterns: cursor, offset, page-based

## Open Questions

1. **Retry Logic:** Should HTTP plugin auto-retry on failure?
   - Pro: Resilient to transient errors
   - Con: May hide real issues, delay failures
   - Decision: Phase 1 no retry, Phase 2 profile-based retry config

2. **Redirect Handling:** Should we follow redirects automatically?
   - Pro: Matches browser behavior
   - Con: May leak credentials across domains
   - Decision: Follow by default, add `--no-follow-redirects` flag

3. **Compression:** Should we handle gzip/brotli automatically?
   - Pro: Faster downloads
   - Con: Added dependency (requests handles this)
   - Decision: Let `requests` library handle automatically

4. **Timeout Defaults:** What's the right default timeout?
   - 30s: Good for most APIs
   - 60s: Better for slow endpoints
   - Decision: 30s default, override via `--timeout`

## Integration Points

### With Profile System
HTTP plugin resolves `@profile/path` references via profile system:
```bash
jn cat @github/repos/owner/repo  # Profile provides base URL + auth
```

### With Format Plugins
HTTP fetches raw data, delegates parsing to format plugins:
```
HTTP (fetch) → Format Plugin (parse) → NDJSON
```

For JSON arrays, HTTP does lightweight parsing to enable streaming.

## Success Criteria

- ✅ Fetch JSON, CSV, NDJSON from HTTP endpoints
- ✅ Stream large responses with constant memory
- ✅ Support authentication (Bearer, Basic, API key)
- ✅ Auto-detect formats from Content-Type and URL
- ✅ Early termination stops download (SIGPIPE)
- ✅ Clear error messages for common failures
- ✅ Integration with profile system

## Future Enhancements

- **Retry logic** with exponential backoff
- **OAuth 2.0** authentication flows
- **Rate limiting** in profiles
- **Pagination** auto-handling
- **GraphQL** query support
- **WebSocket** streaming
- **HTTP/2** and connection pooling

## Dependencies

```toml
dependencies = [
  "requests>=2.31.0"  # HTTP client with streaming
]
```

## Related Documents

- [REST API Profile Design](rest-api-profile-design.md) - Profile system for APIs
- [HTTP Usage Examples](http-usage-examples.md) - Real-world patterns
