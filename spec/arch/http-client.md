# JN — HTTP Client Architecture (curl driver)

**Status:** Design / Implementation Ready
**Updated:** 2025-11-07

---

## Problem Statement

Modern data pipelines need to interact with HTTP APIs for:
- **Sources**: Fetch data from REST APIs, webhooks, data services
- **Targets**: POST results to APIs, webhooks, data warehouses
- **Streaming**: Handle large responses/requests without buffering

**Requirements:**
1. Support standard HTTP methods (GET, POST, PUT, DELETE, PATCH)
2. Stream request/response bodies for O(1) memory usage
3. Handle authentication (Bearer tokens, API keys, Basic auth)
4. Retry logic for transient failures
5. Follow redirects, handle timeouts
6. Work cross-platform (Linux, macOS, Windows)

---

## Design Decision: curl Binary (Not Python httpx)

**Why curl binary:**

✅ **Zero dependencies** - curl ships with every OS
✅ **Streaming built-in** - Pipes work naturally, no buffering
✅ **Battle-tested** - 25+ years handling edge cases (redirects, certs, HTTP/2, auth)
✅ **User familiarity** - Developers already know curl syntax
✅ **Consistent philosophy** - Compose external tools (like jq, jc)
✅ **Simple implementation** - Build argv array, call spawn_exec
✅ **Cross-platform** - Works everywhere, handles Windows quirks

**Why NOT httpx/requests:**
- Additional dependency (~2-5MB)
- Must implement retry, redirect, timeout logic yourself
- Doesn't align with "external tools" philosophy
- More code to maintain
- Async complexity if you want concurrent requests

**When to reconsider:** Only if you need async batch requests or Python-native OAuth flows. Start with curl.

---

## Architecture: curl as Driver

**Pipeline flow:**
```
HTTP Source (curl GET)
  ↓ (stdout pipe, streaming)
Converter (jq: JSON → JSON)
  ↓ (stdout pipe, streaming)
HTTP Target (curl POST, reads stdin)
```

**Key insight:** OS pipes = streaming. curl naturally streams to/from pipes with O(1) memory.

---

## Configuration Model

### Source (GET request)

```json
{
  "name": "api-source",
  "driver": "curl",
  "curl": {
    "method": "GET",
    "url": "https://api.example.com/data?limit=100",
    "headers": {
      "Accept": "application/json",
      "Authorization": "Bearer ${env.API_KEY}"
    },
    "timeout": 30,
    "follow_redirects": true
  }
}
```

### Target (POST request)

```json
{
  "name": "api-target",
  "driver": "curl",
  "curl": {
    "method": "POST",
    "url": "https://api.example.com/ingest",
    "headers": {
      "Content-Type": "application/x-ndjson",
      "Authorization": "Bearer ${env.API_KEY}"
    },
    "body": "stdin",
    "timeout": 60
  }
}
```

### Model Definition

Update `models/drivers.py`:

```python
class CurlSpec(BaseModel):
    """Curl driver specification for HTTP requests."""

    method: str = "GET"
    url: str
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Literal["stdin"] | str | None = None
    timeout: int = 30
    follow_redirects: bool = True
    retry: int = 0
    retry_delay: int = 2
    fail_on_error: bool = True  # Fail on HTTP 4xx/5xx
```

**Notes:**
- `body="stdin"` - Read request body from stdin (for targets)
- `body=None` - No request body (for sources)
- `body="literal string"` - Send literal string as body (rare)
- `retry` - Number of retry attempts (0 = no retry)
- `fail_on_error` - If true, non-2xx responses cause pipeline failure

---

## Implementation: spawn_curl

Create `src/jn/drivers/curl.py`:

```python
"""Curl driver: HTTP client using curl binary."""

import subprocess
from typing import Dict, Literal, Optional

from jn.models import Completed


def spawn_curl(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body: Literal["stdin"] | str | None = None,
    stdin: Optional[bytes] = None,
    timeout: int = 30,
    follow_redirects: bool = True,
    retry: int = 0,
    retry_delay: int = 2,
    fail_on_error: bool = True,
) -> Completed:
    """Execute HTTP request using curl binary.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        url: Full URL including query params
        headers: HTTP headers dict
        body: "stdin" to read from stdin, str for literal body, None for no body
        stdin: Bytes to pass to stdin (for body="stdin")
        timeout: Request timeout in seconds
        follow_redirects: Follow 3xx redirects
        retry: Number of retry attempts (exponential backoff)
        retry_delay: Initial delay between retries (seconds)
        fail_on_error: Fail on HTTP 4xx/5xx status codes

    Returns:
        Completed with response body in stdout

    Notes:
        - For sources: method=GET, body=None, stdin=None
        - For targets: method=POST/PUT, body="stdin", stdin=<data>
        - Streaming: curl naturally streams via pipes (O(1) memory)
    """
    argv = ["curl", "-sS"]  # -s silent, -S show errors

    # HTTP method
    if method != "GET":
        argv.extend(["-X", method])

    # Headers
    for key, value in (headers or {}).items():
        argv.extend(["-H", f"{key}: {value}"])

    # Request body
    if body == "stdin":
        argv.extend(["--data-binary", "@-"])  # Read from stdin
    elif body is not None:
        argv.extend(["-d", body])  # Literal body

    # Timeout
    argv.extend(["--max-time", str(timeout)])

    # Follow redirects
    if follow_redirects:
        argv.append("-L")

    # Retry logic (curl handles exponential backoff)
    if retry > 0:
        argv.extend(["--retry", str(retry)])
        argv.extend(["--retry-delay", str(retry_delay)])

    # Fail on HTTP errors (4xx/5xx)
    if fail_on_error:
        argv.append("-f")  # --fail

    # Show response headers for debugging (optional, can remove)
    # argv.append("-i")  # Include headers in output

    # URL (must be last positional arg)
    argv.append(url)

    # Execute
    result = subprocess.run(
        argv,
        input=stdin,
        capture_output=True,
        check=False,
    )

    return Completed(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


__all__ = ["spawn_curl"]
```

---

## Integration with Pipeline

Update `config/pipeline.py` to handle curl driver:

```python
def _run_source(
    source: Source,
    params: Optional[Dict[str, str]] = None,
    env: Optional[Dict[str, str]] = None,
    unsafe_shell: bool = False,
) -> bytes:
    """Execute a source and return its output bytes."""

    # ... existing exec/shell/file handling ...

    elif source.driver == "curl" and source.curl:
        # Apply templating to URL and headers
        url = substitute_template(source.curl.url, params=params, env=env)
        headers = {
            key: substitute_template(value, params=params, env=env)
            for key, value in source.curl.headers.items()
        }

        result = spawn_curl(
            method=source.curl.method,
            url=url,
            headers=headers,
            timeout=source.curl.timeout,
            follow_redirects=source.curl.follow_redirects,
            retry=source.curl.retry,
            retry_delay=source.curl.retry_delay,
            fail_on_error=source.curl.fail_on_error,
        )
        _check_result("source", source.name, result)
        return result.stdout

    raise NotImplementedError(f"Driver {source.driver} not implemented")


def _run_target(
    target: Target,
    stdin: bytes,
    params: Optional[Dict[str, str]] = None,
    env: Optional[Dict[str, str]] = None,
    unsafe_shell: bool = False,
) -> bytes:
    """Execute a target and return its output bytes."""

    # ... existing exec/shell/file handling ...

    elif target.driver == "curl" and target.curl:
        # Apply templating to URL and headers
        url = substitute_template(target.curl.url, params=params, env=env)
        headers = {
            key: substitute_template(value, params=params, env=env)
            for key, value in target.curl.headers.items()
        }

        result = spawn_curl(
            method=target.curl.method,
            url=url,
            headers=headers,
            body=target.curl.body,
            stdin=stdin,
            timeout=target.curl.timeout,
            follow_redirects=target.curl.follow_redirects,
            retry=target.curl.retry,
            retry_delay=target.curl.retry_delay,
            fail_on_error=target.curl.fail_on_error,
        )
        _check_result("target", target.name, result)
        return result.stdout

    raise NotImplementedError(f"Driver {target.driver} not implemented")
```

---

## CLI Usage

### Create HTTP Source

```bash
# Simple GET
jn new source curl api-get \
  --url "https://api.example.com/data" \
  --jn ./jn.json

# With authentication
jn new source curl github-repos \
  --url "https://api.github.com/users/octocat/repos" \
  --header "Accept: application/vnd.github.v3+json" \
  --header "Authorization: Bearer ${env.GITHUB_TOKEN}" \
  --jn ./jn.json

# With retry
jn new source curl flaky-api \
  --url "https://api.example.com/data" \
  --retry 3 \
  --retry-delay 5 \
  --timeout 60 \
  --jn ./jn.json
```

### Create HTTP Target

```bash
# POST NDJSON to webhook
jn new target curl webhook \
  --method POST \
  --url "https://webhook.site/unique-id" \
  --header "Content-Type: application/x-ndjson" \
  --jn ./jn.json

# POST to API with auth
jn new target curl api-ingest \
  --method POST \
  --url "https://api.example.com/ingest" \
  --header "Content-Type: application/json" \
  --header "Authorization: Bearer ${env.API_KEY}" \
  --jn ./jn.json
```

### CLI Flags

Add to `src/jn/cli/new/source.py` and `target.py`:

```python
# HTTP-specific flags
url: Optional[str] = typer.Option(None, "--url", help="HTTP URL")
method: Optional[str] = typer.Option(None, "--method", help="HTTP method (GET, POST, etc.)")
header: Optional[List[str]] = typer.Option(None, "--header", help="HTTP header (Key: Value)")
timeout: Optional[int] = typer.Option(None, "--timeout", help="Request timeout (seconds)")
retry: Optional[int] = typer.Option(None, "--retry", help="Retry attempts")
```

---

## Complete End-to-End Example

**Use case:** Fetch top Hacker News stories, filter by points, POST to webhook

```bash
# Initialize
jn init --jn ./jn.json

# Source: HN Algolia API (no auth required)
jn new source curl hn-stories \
  --url "https://hn.algolia.com/api/v1/search_by_date?tags=story&hitsPerPage=50" \
  --header "Accept: application/json" \
  --jn ./jn.json

# Converter: Extract and filter high-scoring stories
jn new converter top-stories \
  --expr '.hits[] | select(.points > 100) | {title, url, points, author}' \
  --jn ./jn.json

# Target: POST to httpbin for testing
jn new target curl httpbin \
  --method POST \
  --url "https://httpbin.org/post" \
  --header "Content-Type: application/x-ndjson" \
  --jn ./jn.json

# Create pipeline
jn new pipeline hn-to-httpbin \
  --source hn-stories \
  --converter top-stories \
  --target httpbin \
  --jn ./jn.json

# Run
jn run hn-to-httpbin --jn ./jn.json
```

**What happens:**
1. curl GETs from HN API → JSON array
2. jq filters and transforms → NDJSON stream
3. curl POSTs each line → httpbin echoes back

**Memory usage:** O(1) - everything streams through pipes

---

## Streaming Guarantees

### Source Streaming (GET large responses)

**curl naturally streams:**
```bash
curl -N -sS "https://api.example.com/stream"
```

The `-N` flag (no buffering) ensures curl writes to stdout as data arrives. Combined with jq's streaming mode, you can process infinite streams:

```bash
curl -N "https://stream-api.example.com/events" | jq -c '.event'
```

**For JN:** No special handling needed. curl writes to pipe, jq reads from pipe, all streaming.

### Target Streaming (POST large requests)

**curl reads stdin incrementally:**
```bash
jq -c '...' | curl -X POST --data-binary @- "https://api.example.com/ingest"
```

The `@-` tells curl to read from stdin. It doesn't buffer the entire input - it reads chunks and sends them incrementally.

**Memory:** Only limited by OS pipe buffer size (~64KB), not data size.

---

## Authentication Patterns

### 1. Bearer Token (OAuth, API Keys)

```json
{
  "headers": {
    "Authorization": "Bearer ${env.API_KEY}"
  }
}
```

**Usage:**
```bash
export API_KEY="sk_live_abc123..."
jn run api-pipeline --jn ./jn.json
```

### 2. API Key in Header

```json
{
  "headers": {
    "X-API-Key": "${env.API_KEY}"
  }
}
```

### 3. API Key in Query String

```json
{
  "url": "https://api.example.com/data?api_key=${params.key}"
}
```

**Usage:**
```bash
jn run api-pipeline --param key=abc123 --jn ./jn.json
```

### 4. Basic Auth (Future Enhancement)

Could add dedicated field:
```json
{
  "curl": {
    "url": "...",
    "basic_auth": {
      "username": "${env.API_USER}",
      "password": "${env.API_PASS}"
    }
  }
}
```

Translates to: `curl -u "${username}:${password}"`

---

## Error Handling

### HTTP Status Codes

**With `fail_on_error: true` (default):**
- 2xx: Success, continue pipeline
- 3xx: Follow redirects (if enabled), else fail
- 4xx/5xx: Fail pipeline with error

**With `fail_on_error: false`:**
- All responses pass through (even errors)
- Useful for testing or when you want to handle errors in jq

**Example error output:**
```
Error: ('source', 'api-get', 22, 'curl: (22) The requested URL returned error: 404')
```

### Network Errors

**Timeouts:**
```json
{"timeout": 30}  // Fail after 30 seconds
```

**Retries:**
```json
{
  "retry": 3,           // Retry up to 3 times
  "retry_delay": 2      // Wait 2s, then 4s, then 8s (exponential backoff)
}
```

curl handles exponential backoff automatically.

### SSL/TLS Errors

**Default:** curl validates SSL certificates

**To disable (testing only):**
Could add `insecure: true` flag → translates to `curl -k`

**Not recommended for production!**

---

## Testing Strategy

### Unit Tests

**Test curl driver in isolation** (`tests/unit/test_curl_driver.py`):

```python
def test_spawn_curl_get():
    result = spawn_curl(
        method="GET",
        url="https://httpbin.org/get",
    )
    assert result.returncode == 0
    assert b'"url": "https://httpbin.org/get"' in result.stdout

def test_spawn_curl_post_with_stdin():
    data = b'{"test": "data"}'
    result = spawn_curl(
        method="POST",
        url="https://httpbin.org/post",
        body="stdin",
        stdin=data,
        headers={"Content-Type": "application/json"},
    )
    assert result.returncode == 0
    assert b'"test": "data"' in result.stdout

def test_spawn_curl_headers():
    result = spawn_curl(
        method="GET",
        url="https://httpbin.org/headers",
        headers={"X-Custom": "value"},
    )
    assert result.returncode == 0
    assert b'"X-Custom": "value"' in result.stdout

def test_spawn_curl_timeout():
    # httpbin /delay/10 waits 10 seconds
    result = spawn_curl(
        method="GET",
        url="https://httpbin.org/delay/10",
        timeout=2,  # Timeout after 2 seconds
    )
    assert result.returncode != 0  # Should timeout
    assert b"timeout" in result.stderr.lower()

def test_spawn_curl_retry():
    # First requests to httpbin may be slow, test retry logic
    result = spawn_curl(
        method="GET",
        url="https://httpbin.org/status/500",  # Always returns 500
        retry=2,
        fail_on_error=True,
    )
    assert result.returncode != 0  # Should fail after retries
```

### Integration Tests

**End-to-end pipeline tests** (`tests/integration/test_curl_source.py`):

```python
def test_curl_source_to_target_pipeline(runner, tmp_path):
    """Test HTTP GET → jq → HTTP POST pipeline."""

    jn_path = tmp_path / "jn.json"
    init_config(runner, jn_path)

    # Source: Get HN top stories
    result = runner.invoke(app, [
        "new", "source", "curl", "hn",
        "--url", "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=5",
        "--jn", str(jn_path)
    ])
    assert result.exit_code == 0

    # Converter: Extract titles
    add_converter(runner, jn_path, "titles", ".hits[].title")

    # Target: POST to httpbin
    result = runner.invoke(app, [
        "new", "target", "curl", "httpbin",
        "--method", "POST",
        "--url", "https://httpbin.org/post",
        "--header", "Content-Type: text/plain",
        "--jn", str(jn_path)
    ])
    assert result.exit_code == 0

    # Pipeline
    add_pipeline(runner, jn_path, "hn-to-httpbin", [
        "source:hn", "converter:titles", "target:httpbin"
    ])

    # Run
    result = runner.invoke(app, ["run", "hn-to-httpbin", "--jn", str(jn_path)])

    assert result.exit_code == 0
    # httpbin echoes back what we sent
    assert "data" in result.output


def test_curl_streaming_source(runner, tmp_path):
    """Test streaming HTTP source (httpbin /stream/N)."""

    jn_path = tmp_path / "jn.json"
    init_config(runner, jn_path)

    # Source: httpbin streaming endpoint (10 JSON objects)
    result = runner.invoke(app, [
        "new", "source", "curl", "stream",
        "--url", "https://httpbin.org/stream/10",
        "--jn", str(jn_path)
    ])
    assert result.exit_code == 0

    # Converter: Pass through
    add_converter(runner, jn_path, "pass", ".")

    # Target: cat to stdout
    add_exec_target(runner, jn_path, "cat", ["cat"])

    # Pipeline
    add_pipeline(runner, jn_path, "stream-test", [
        "source:stream", "converter:pass", "target:cat"
    ])

    # Run
    result = runner.invoke(app, ["run", "stream-test", "--jn", str(jn_path)])

    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 10  # Should have 10 JSON objects


@pytest.mark.skipif(os.getenv("JN_OFFLINE") == "1", reason="Network test")
def test_curl_with_auth_header(runner, tmp_path):
    """Test curl with Authorization header."""

    jn_path = tmp_path / "jn.json"
    init_config(runner, jn_path)

    # Source with auth header (httpbin echoes headers)
    result = runner.invoke(app, [
        "new", "source", "curl", "auth-test",
        "--url", "https://httpbin.org/bearer",
        "--header", "Authorization: Bearer test-token-123",
        "--jn", str(jn_path)
    ])
    assert result.exit_code == 0

    # Converter: Extract token
    add_converter(runner, jn_path, "token", ".token")

    # Target: stdout
    add_exec_target(runner, jn_path, "cat", ["cat"])

    # Pipeline
    add_pipeline(runner, jn_path, "auth", [
        "source:auth-test", "converter:token", "target:cat"
    ])

    # Run
    result = runner.invoke(app, ["run", "auth", "--jn", str(jn_path)])

    assert result.exit_code == 0
    assert "test-token-123" in result.output
```

---

## Free Test APIs (No Authentication)

Perfect for development and testing:

### Data Sources (GET)
- **httpbin.org** - Echo service, `/get`, `/headers`, `/stream/N`
- **Hacker News Algolia** - `hn.algolia.com/api/v1/search?query=...`
- **SpaceX API** - `api.spacexdata.com/v4/launches/latest`
- **Open-Meteo** - `api.open-meteo.com/v1/forecast?latitude=...`
- **JSONPlaceholder** - `jsonplaceholder.typicode.com/posts`

### Echo Services (POST)
- **httpbin.org** - `/post`, `/put`, `/patch`, `/delete`
- **Postman Echo** - `postman-echo.com/post`
- **ReqRes** - `reqres.in/api/users` (fake persistence)

### JSON Storage (Persist Data)
- **JSONStorage.net** - No auth required for testing
- **Pantry** - `getpantry.cloud` (get free pantry ID)

---

## Network Test Policy

**In CI, guard with environment flag:**

```python
import os
import pytest

@pytest.mark.skipif(
    os.getenv("JN_OFFLINE") == "1",
    reason="Network test disabled in offline mode"
)
def test_http_request():
    # ... test that hits external API
```

**Run locally:**
```bash
pytest                    # Includes network tests
JN_OFFLINE=1 pytest      # Skips network tests
```

---

## Performance Considerations

### Concurrent Requests (Future)

**Current:** Sequential execution (one request at a time)
**Future:** Could add parallel source support:

```bash
# Multiple sources in parallel
jn run pipeline --parallel-sources
```

Would require process pool or asyncio. **Defer until needed.**

### Connection Reuse

**Current:** Each curl invocation creates new connection
**Future:** Could use curl connection pooling with `--keepalive-time`

Not a concern unless making hundreds of requests. **Defer until needed.**

### Large Payloads

**Streaming handles this naturally:**
- GET 10GB file → pipes through jq → POST incrementally
- Memory usage: O(1) regardless of size

**Only limitation:** Disk space if writing to file target

---

## Roadmap

### Phase 1: Core Implementation ✅ (This Design)
- Basic HTTP methods (GET, POST, PUT, DELETE)
- Headers, timeout, retry
- Streaming via pipes
- Template substitution for URLs/headers
- CLI integration

### Phase 2: Enhanced Features (Future)
- Basic auth shortcut (`username`/`password` fields)
- Custom CA certificates (`ca_cert` field)
- Proxy support (`proxy` field)
- Response code capture (expose HTTP status to jq)
- Request/response logging (debug mode)

### Phase 3: Advanced (If Needed)
- Multipart uploads
- Cookie jar persistence
- Client certificates
- HTTP/2 Server Push
- WebSocket upgrade (probably separate driver)

---

## Security Considerations

### Secrets in Configuration

**Problem:** API keys in config files

**Solution:** Template substitution with environment variables

```json
{
  "headers": {
    "Authorization": "Bearer ${env.API_KEY}"
  }
}
```

**Best practice:**
- Never commit secrets to jn.json
- Use ${env.*} for all secrets
- Document required env vars in README

### SSL/TLS Validation

**Default:** curl validates certificates (secure)

**Insecure mode (testing only):**
```json
{"insecure": true}  // Disables cert validation
```

**Warning:** Only use for local development, never production

### Rate Limiting

**Problem:** Overwhelming APIs with requests

**Solution:** Add delay between retries, respect 429 responses

**Future:** Could add `rate_limit` field (requests per second)

---

## Comparison to Alternatives

### vs Python requests/httpx

| Feature | curl binary | httpx/requests |
|---------|-------------|----------------|
| Dependencies | ✅ None | ❌ 2-5MB package |
| Streaming | ✅ Native pipes | ⚠️ Requires streaming=True |
| Memory | ✅ O(1) | ⚠️ Can buffer in memory |
| Retry logic | ✅ Built-in | ❌ Must implement |
| Redirects | ✅ Built-in | ⚠️ Partial |
| Auth | ✅ All methods | ✅ All methods |
| Philosophy fit | ✅ External tools | ❌ Python-native |
| Implementation | ✅ ~100 lines | ❌ ~500 lines |

**Recommendation:** Start with curl, only switch if you need async batching.

### vs wget

**curl wins:**
- Better for APIs (cleaner syntax, better header handling)
- Streaming to stdout is default
- More flexible (custom methods, inline data)

**wget better for:**
- Recursive downloads
- Resuming interrupted downloads
- Mirroring websites

**For JN pipelines:** curl is the right choice.

---

## Open Questions / Future Considerations

1. **Response code handling:**
   - Should we expose HTTP status code to jq? (e.g., `.http_status`)
   - How to handle redirects? (Follow automatically or expose redirect chain?)

2. **Authentication helpers:**
   - Add `basic_auth` field for convenience?
   - OAuth 2.0 flow support? (Probably not - too complex)

3. **Content negotiation:**
   - Auto-set Accept/Content-Type based on data format?
   - Or force explicit headers? (Current approach)

4. **Rate limiting:**
   - Built-in rate limiter (requests per second)?
   - Or let users handle via sleep in shell wrapper?

5. **Response headers:**
   - Capture response headers for downstream processing?
   - Useful for pagination (Link headers), ETags, etc.

---

## References

- curl documentation: https://curl.se/docs/
- httpbin API: https://httpbin.org/
- HTTP status codes: https://httpstatuses.com/
- NDJSON spec: http://ndjson.org/
- Driver architecture: `spec/arch/drivers.md`

---

## Summary

**Recommendation:** Implement curl driver using curl binary.

**Why:**
1. ✅ Zero dependencies (curl everywhere)
2. ✅ Streaming built-in (O(1) memory)
3. ✅ Simple implementation (~100 lines)
4. ✅ Aligns with external tools philosophy
5. ✅ Battle-tested (25 years of edge cases handled)

**Configuration:**
- Add timeout, retry, headers support
- Template substitution for secrets (${env.*})
- Streaming via stdin/stdout pipes

**Testing:**
- Use httpbin, HN API, Open-Meteo (free, no auth)
- Guard network tests with JN_OFFLINE flag
- Test streaming with /stream/N endpoint

**Implementation time:** 3-4 hours for basic version + tests

**Next steps:**
1. Implement spawn_curl in drivers/curl.py
2. Integrate with _run_source and _run_target
3. Add CLI flags to new/source.py and new/target.py
4. Write integration tests with httpbin
5. Update roadmap to mark complete
