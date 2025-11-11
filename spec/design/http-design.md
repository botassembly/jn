# HTTP Plugin - Design

## Overview

HTTP protocol plugin for fetching data from web APIs, remote files, and cloud services. Enables JN to work with HTTP/HTTPS endpoints using streaming architecture and automatic format detection.

## Why HTTP Plugin?

Most modern data sources are accessible via HTTP. APIs, cloud storage, and remote files all use HTTP/HTTPS as transport. This plugin makes JN a universal data tool that can fetch from anywhere.

## Core Concepts

### Sources, Filters, Targets

**Sources** (`jn cat`):
- Fetch data from HTTP endpoints
- Output NDJSON to stdout
- Can be piped to filters or targets

**Filters** (`jn filter`):
- Transform NDJSON streams
- Multiple filters can chain
- source → filter → filter → target

**Targets** (`jn put`):
- Write NDJSON to files or stdout
- Format conversion (CSV, JSON, tables)

**Pipeline:** `cat @api/endpoint | filter '.field > 100' | put output.csv`

### Plugin Type

**Protocol plugin** - `reads()` only

HTTP is a *source* - it fetches data and emits NDJSON. Writing via HTTP (POST/PUT) is handled through method parameters, not `writes()`.

### Pattern Matching

```toml
matches = ["^https?://.*"]
```

Matches any URL starting with `http://` or `https://`

## Key Design Decisions

### 1. Automatic Format Detection

Detect response format via:
- Content-Type header (`application/json`, `text/csv`)
- URL file extension (`.json`, `.csv`)
- Manual override (`--format json`)

**Why:** Users shouldn't specify format twice. If they fetch `data.csv`, assume CSV.

**Example:**
```bash
jn cat https://example.com/data.json  # Auto-detects JSON
jn cat https://example.com/data.csv   # Auto-detects CSV
jn cat https://example.com/data --format json  # Override
```

### 2. Streaming Architecture

Process responses line-by-line with constant memory, regardless of size.

**Why:** Enables processing GB-sized responses without buffering. Early termination (`| head -n 10`) stops download immediately.

**Example:**
```bash
# Only downloads/processes first 10 records
jn cat https://api.example.com/large-dataset | head -n 10
```

### 3. JSON Array Handling

JSON arrays yield one NDJSON record per element:
```json
[{"id": 1}, {"id": 2}]  →  {"id": 1}\n{"id": 2}\n
```

**Why:** Consistent with NDJSON philosophy - one record per line enables streaming and piping.

### 4. Authentication via Profiles

Headers, tokens, and credentials managed by REST API profiles (see `rest-api-profiles.md`).

**Why:** Separates concerns - HTTP handles transport, profiles handle auth/credentials.

## Features

- **Methods:** GET, POST, PUT, DELETE
- **Auth:** Bearer tokens, Basic auth, API keys, custom headers
- **Format detection:** JSON, CSV, NDJSON, text
- **Streaming:** Constant memory for large responses
- **Error handling:** HTTP errors, timeouts, SSL failures
- **Profile integration:** `@profile/path` syntax

## Usage Examples

### Basic HTTP GET

```bash
# Fetch JSON
jn cat https://opencode.ai/config.json

# Fetch CSV
jn cat https://example.com/data.csv

# Fetch and filter
jn cat https://api.example.com/users | jn filter '.age > 30'
```

### With Authentication

```bash
# Bearer token (direct)
jn cat https://api.example.com/data \
  --headers '{"Authorization": "Bearer ${API_TOKEN}"}'

# Basic auth
jn cat https://api.example.com/secure --auth "user:pass"

# API key header
jn cat https://api.example.com/data \
  --headers '{"X-API-Key": "${API_KEY}"}'
```

### HTTP POST

```bash
# POST JSON payload
echo '{"query": "test"}' | \
  jn cat https://api.example.com/search --method POST

# POST form data
jn cat https://api.example.com/form \
  --method POST \
  --data "key1=value1&key2=value2"
```

### Profile-Based (Clean Syntax)

```bash
# Credentials from profile
jn cat @github/repos/microsoft/vscode/issues

# With path parameters
jn cat @api/users/{id} --id 123

# Chain with filters
jn cat @github/repos/owner/repo/issues | \
  jn filter '.state == "open"' | \
  jn put issues.csv
```

See `rest-api-profiles.md` for profile system design.

### Multi-Stage Pipelines

```bash
# Fetch → Filter → Transform → Display
jn cat @api/products | \
  jn filter '.price > 100' | \
  jn filter '{name, price, category}' | \
  jn put --plugin tabulate --tablefmt grid -

# Fetch → Save
jn cat @api/data | jn put output.json

# Fetch → Filter → Convert
jn cat https://api.example.com/users | \
  jn filter '.active == true' | \
  jn put users.csv
```

## Implementation Details

### Request Flow

1. **Parse URL/profile** - Extract endpoint, resolve profile if `@profile/path`
2. **Build request** - Construct headers, auth, method, body
3. **Execute** - Make HTTP request with `requests` library
4. **Detect format** - Check Content-Type and URL extension
5. **Stream** - Parse response incrementally, yield NDJSON

### Format Handlers

**JSON:**
- Arrays: yield each element as record
- Objects: yield single record
- Primitives: wrap in `{"value": ...}`

**NDJSON:**
- Stream line-by-line
- Parse each line as JSON

**CSV:**
- Yield as single record: `{"content": "...", "content_type": "text/csv"}`
- User pipes to CSV plugin for parsing

**Text:**
- Yield as single record: `{"content": "...", "content_type": "text/plain"}`

### Error Handling

```python
try:
    response = requests.get(url, timeout=30, stream=True)
    response.raise_for_status()
except requests.HTTPError as e:
    print(f"HTTP Error: {e}", file=sys.stderr)
    sys.exit(1)
except requests.Timeout:
    print(f"Timeout fetching {url}", file=sys.stderr)
    sys.exit(1)
```

## Risks & Challenges

### 1. Format Detection Ambiguity
**Risk:** Server returns wrong Content-Type or no extension in URL.

**Mitigation:**
- Fallback: Attempt JSON parse, then treat as text
- Allow `--format` override
- Heuristic detection (starts with `{` or `[`)

### 2. Memory Issues with Large Responses
**Risk:** Downloading GB file without streaming.

**Mitigation:**
- Use `stream=True` in requests
- Process line-by-line for NDJSON/CSV
- Document that JSON arrays are buffered (need entire response to parse)

### 3. Authentication Complexity
**Risk:** Every API has different auth (OAuth, JWT, API keys, etc.).

**Mitigation:**
- Support common patterns (Bearer, Basic, headers)
- Complex flows (OAuth refresh) handled by profiles
- Document common patterns

### 4. SSL Certificate Issues
**Risk:** Self-signed certs, expired certs block requests.

**Mitigation:**
- Default: verify SSL
- Option: `--no-verify-ssl` flag (with warning)
- Document security implications

### 5. Rate Limiting
**Risk:** APIs throttle requests.

**Mitigation:**
- Document retry strategies
- Consider adding `--retry` flag
- Let users handle with external tools (sleep, retry loops)

### 6. Binary/Non-Text Responses
**Risk:** Images, PDFs, binary data can't convert to NDJSON.

**Mitigation:**
- Detect binary Content-Type
- Yield metadata: `{"url": "...", "content_type": "image/png", "size": 1024}`
- Stream to file instead of stdout (future enhancement)

### 7. Pagination
**Risk:** APIs return paginated data.

**Mitigation:**
- Phase 1: User handles manually (`?page=2`)
- Phase 2: Profile-based pagination config (auto-follow `next` links)

### 8. Large JSON Arrays
**Risk:** Can't stream JSON arrays without streaming JSON parser.

**Mitigation:**
- Accept limitation: JSON arrays buffer entire response
- Recommend NDJSON for large datasets
- Document memory implications

## Open Questions

### 1. Response Caching?
Should HTTP plugin cache responses?

**Options:**
- **No caching** (current) - Simple, predictable
- **Optional cache** - `--cache` flag, store in `/tmp`
- **Profile-based** - Cache config in profile

**Trade-off:** Complexity vs. performance for repeated queries.

**Recommendation:** No caching initially. Add if needed.

### 2. Automatic Pagination?
Should profiles support auto-pagination?

**Example:**
```json
{
  "pagination": {
    "next_link": "$.pagination.next",
    "auto_follow": true
  }
}
```

**Trade-off:** Convenience vs. complexity and unexpected behavior.

**Recommendation:** Phase 2 feature after basic profiles proven.

### 3. POST Form Data?
How to handle form-encoded POST (vs JSON)?

**Options:**
- **Flag:** `--form-data "key1=value1&key2=value2"`
- **Detect:** If stdin is key=value format, use form encoding
- **Profile:** Form data in profile config

**Recommendation:** Support `--form-data` flag for common use case.

### 4. Streaming JSON Arrays?
Can we stream large JSON arrays?

**Options:**
- **ijson library** - Streaming JSON parser (adds dependency)
- **Document limitation** - Recommend NDJSON for large data
- **Phase 2** - Add streaming JSON if demand exists

**Recommendation:** Document limitation. Most APIs support NDJSON.

---

## Related Documents

- `rest-api-profiles.md` - Profile system for clean API access
- `format-design.md` - How format plugins work
- `genomoncology-api.md` - Real-world API example with sources/filters

## Next Steps

1. **Implement POST form data** - Add `--form-data` flag
2. **Enhance error messages** - Better HTTP error descriptions
3. **Add retry logic** - `--retry N` for transient failures
4. **Document common APIs** - Examples for GitHub, Stripe, AWS
5. **Profile pagination** - Auto-follow next links (Phase 2)
