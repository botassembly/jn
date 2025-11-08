# JN — HTTP Client Architecture (curl driver)

**Status:** ✅ Implemented (2025-11-08)
**Location:** `src/jn/drivers/curl.py`

---

## Problem Statement

Modern data pipelines need HTTP APIs for:
- **Sources**: Fetch from REST APIs, webhooks, data services
- **Targets**: POST results to APIs, webhooks, warehouses
- **Streaming**: Handle large payloads without buffering

---

## Design Decision: curl Binary (Not Python httpx)

**Why curl binary:**
- ✅ Zero dependencies (ships with every OS)
- ✅ Streaming built-in (pipes work naturally, O(1) memory)
- ✅ Battle-tested (25+ years handling redirects, certs, HTTP/2, auth)
- ✅ Aligns with "external tools" philosophy (like jq, jc)
- ✅ Simple (~100 lines vs ~500 lines for httpx)

**Why NOT httpx/requests:**
- Additional dependency (~2-5MB)
- Must implement retry/redirect/timeout yourself
- Doesn't fit "compose external tools" philosophy

**When to reconsider:** Only if you need async batch requests or Python-native OAuth flows.

---

## Configuration

### Source Example (GET)
```json
{
  "name": "api-source",
  "driver": "curl",
  "curl": {
    "method": "GET",
    "url": "https://api.example.com/data",
    "headers": {
      "Authorization": "Bearer ${env.API_KEY}"
    },
    "timeout": 30,
    "retry": 3,
    "follow_redirects": true,
    "fail_on_error": true
  }
}
```

### Target Example (POST)
```json
{
  "name": "webhook",
  "driver": "curl",
  "curl": {
    "method": "POST",
    "url": "https://webhook.site/xyz",
    "headers": {
      "Content-Type": "application/x-ndjson"
    },
    "body": "stdin"
  }
}
```

**Key fields:**
- `body: "stdin"` - Read request body from stdin (for targets)
- `retry` - Retry attempts with exponential backoff
- `fail_on_error` - Fail on HTTP 4xx/5xx (default: true)

---

## CLI Usage

```bash
# Create HTTP source
jn new source curl hn-api \
  --url "https://hn.algolia.com/api/v1/search?query=python" \
  --header "Accept: application/json" \
  --retry 3

# Create HTTP target
jn new target curl webhook \
  --method POST \
  --url "https://webhook.site/unique-id" \
  --header "Content-Type: application/x-ndjson"

# Run pipeline: API → jq → webhook
jn run my-pipeline
```

**Flags:** `--url`, `--method`, `--header`, `--timeout`, `--retry`, `--allow-errors`

---

## Authentication Patterns

**Bearer Token:**
```json
{"headers": {"Authorization": "Bearer ${env.API_KEY}"}}
```

**API Key Header:**
```json
{"headers": {"X-API-Key": "${env.API_KEY}"}}
```

**Query String:**
```json
{"url": "https://api.example.com/data?key=${params.api_key}"}
```

**Best practice:** Never commit secrets. Use `${env.*}` for all credentials.

---

## Streaming & Memory

**Key insight:** OS pipes = streaming. curl naturally streams via pipes with O(1) memory.

```
HTTP Source (curl GET)
  ↓ (stdout pipe, streaming)
Converter (jq filter)
  ↓ (stdout pipe, streaming)
HTTP Target (curl POST from stdin)
```

**Memory usage:** Only limited by OS pipe buffer (~64KB), not data size. Can process GB+ payloads.

---

## Error Handling

**HTTP Status Codes:**
- `fail_on_error: true` (default): 4xx/5xx fail pipeline
- `fail_on_error: false`: All responses pass through (useful for testing)

**Retry Logic:**
- Exponential backoff handled by curl automatically
- Configure with `retry` and `retry_delay` fields

**Example error:**
```
Error: ('source', 'api-get', 22, 'curl: (22) The requested URL returned error: 404')
```

---

## Testing Strategy

**Unit tests** (with mocked subprocess):
- Test argv construction for all methods/flags
- No network required, fast and deterministic
- See: `tests/unit/test_curl_driver.py`

**Integration tests** (with real HTTP):
- Guard with `JN_OFFLINE=1` env flag to skip in CI
- Use free APIs: httpbin.org, hn.algolia.com
- See: `tests/integration/test_curl_driver.py`

---

## Future Enhancements (Deferred)

- **Basic auth shortcut** (`username`/`password` fields)
- **Custom CA certificates** (`ca_cert` field)
- **Proxy support** (`proxy` field)
- **Response status capture** (expose HTTP status to jq)
- **Parallel requests** (process pool for multiple sources)

**Decision:** Implement when needed, not speculatively.

---

## References

- curl docs: https://curl.se/docs/
- Driver architecture: `spec/arch/drivers.md`
- Implementation: `src/jn/drivers/curl.py`
- CLI: `src/jn/cli/new/source.py`, `src/jn/cli/new/target.py`
