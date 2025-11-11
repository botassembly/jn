# HTTP Protocol Plugin - Design Document

## Overview

HTTP protocol plugin for fetching data from HTTP/HTTPS endpoints. Supports JSON, CSV, and other formats with automatic content-type detection.

## Core Design

### Plugin Type
**Protocol plugin** with `reads()` function only (no writes - HTTP PUT/POST handled via profiles)

### Pattern Matching
```toml
[tool.jn]
matches = [
  "^https?://.*",
  "^http://.*"
]
```

### Dependencies
```toml
dependencies = [
  "requests>=2.31.0",
  "urllib3>=2.0.0"
]
```

## Functionality

### 1. Basic GET Request
```bash
# Fetch JSON and parse automatically
jn cat https://opencode.ai/config.json

# Fetch CSV and parse automatically
jn cat https://example.com/data.csv

# Fetch and save raw response
jn cat https://example.com/image.png --raw | base64
```

### 2. Content-Type Detection
The plugin detects format via:
1. **Content-Type header** (e.g., `application/json`, `text/csv`)
2. **URL file extension** (e.g., `.json`, `.csv`, `.xml`)
3. **--format flag override** (e.g., `--format json`)

### 3. Response Handling

**Automatic parsing flow:**
```
HTTP fetch → Detect content type → Parse format → Output NDJSON
```

**For JSON responses:**
```json
// Response: {"users": [{"name": "Alice"}, {"name": "Bob"}]}
// Output NDJSON:
{"users": [{"name": "Alice"}, {"name": "Bob"}]}
```

**For JSON arrays:**
```json
// Response: [{"name": "Alice"}, {"name": "Bob"}]
// Output NDJSON (one record per array element):
{"name": "Alice"}
{"name": "Bob"}
```

**For CSV responses:**
```csv
name,age
Alice,30
Bob,25
```
Output NDJSON:
```json
{"name": "Alice", "age": "30"}
{"name": "Bob", "age": "25"}
```

### 4. Configuration Options

```python
def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Fetch HTTP endpoint and parse response to NDJSON.

    Config:
        method: HTTP method (default: 'GET')
        headers: Dict of HTTP headers
        params: Dict of query parameters
        data: Request body (for POST/PUT)
        auth: Tuple of (username, password) for basic auth
        timeout: Request timeout in seconds (default: 30)
        format: Force format detection ('json', 'csv', 'xml', 'text')
        raw: Output raw bytes without parsing (default: False)
        follow_redirects: Follow HTTP redirects (default: True)
        verify_ssl: Verify SSL certificates (default: True)
    """
```

## Usage Examples

### Example 1: Fetch JSON API
```bash
# Simple GET
jn cat https://opencode.ai/config.json

# With query parameters
jn cat https://api.example.com/users --params '{"status":"active"}'

# Save to file
jn cat https://api.example.com/data.json | jn put data.csv
```

### Example 2: Headers and Authentication
```bash
# Custom headers
jn cat https://api.example.com/data \
  --headers '{"Authorization": "Bearer ${API_TOKEN}"}'

# Basic auth
jn cat https://api.example.com/secure \
  --auth "user:pass"
```

### Example 3: POST Request
```bash
# POST JSON data
jn cat https://api.example.com/search \
  --method POST \
  --data '{"query": "test"}' \
  --headers '{"Content-Type": "application/json"}'
```

### Example 4: Format Override
```bash
# Force JSON parsing even if Content-Type is wrong
jn cat https://example.com/data.txt --format json

# Get raw response (no parsing)
jn cat https://example.com/data.json --raw > response.json
```

## Implementation Details

### Plugin Structure
```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests>=2.31.0"
# ]
# [tool.jn]
# matches = ["^https?://.*"]
# ///

import json
import sys
import requests
from typing import Iterator, Optional
from urllib.parse import urlparse

def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Fetch HTTP endpoint and parse to NDJSON."""
    config = config or {}

    # Parse URL from stdin (for jn cat URL) or config
    url = config.get('url') or sys.stdin.read().strip()

    # Request configuration
    method = config.get('method', 'GET')
    headers = config.get('headers', {})
    params = config.get('params', {})
    data = config.get('data')
    auth = config.get('auth')
    timeout = config.get('timeout', 30)
    verify_ssl = config.get('verify_ssl', True)

    # Make HTTP request
    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        params=params,
        data=data,
        auth=tuple(auth.split(':', 1)) if isinstance(auth, str) else auth,
        timeout=timeout,
        verify=verify_ssl,
        stream=True
    )
    response.raise_for_status()

    # Detect format
    format_type = detect_format(response, url, config)

    # Parse and yield records
    if format_type == 'json':
        yield from parse_json_response(response)
    elif format_type == 'csv':
        yield from parse_csv_response(response)
    elif format_type == 'ndjson':
        yield from parse_ndjson_response(response)
    elif format_type == 'raw':
        # Output raw response as single record with content
        yield {"url": url, "content": response.text, "status": response.status_code}
    else:
        # Unknown format - output as text
        yield {"url": url, "text": response.text}

def detect_format(response, url, config):
    """Detect response format from Content-Type, URL, or config."""
    # Config override
    if 'format' in config:
        return config['format']

    # Content-Type header
    content_type = response.headers.get('Content-Type', '').lower()
    if 'application/json' in content_type:
        return 'json'
    elif 'text/csv' in content_type:
        return 'csv'
    elif 'application/x-ndjson' in content_type:
        return 'ndjson'

    # URL file extension
    path = urlparse(url).path
    if path.endswith('.json'):
        return 'json'
    elif path.endswith('.csv'):
        return 'csv'
    elif path.endswith('.ndjson') or path.endswith('.jsonl'):
        return 'ndjson'

    # Default to JSON for APIs
    return 'json'

def parse_json_response(response) -> Iterator[dict]:
    """Parse JSON response to NDJSON records."""
    data = response.json()

    if isinstance(data, list):
        # Array of objects - yield each element
        for item in data:
            if isinstance(item, dict):
                yield item
            else:
                yield {"value": item}
    elif isinstance(data, dict):
        # Single object - yield as-is
        yield data
    else:
        # Primitive value
        yield {"value": data}

def parse_csv_response(response) -> Iterator[dict]:
    """Parse CSV response to NDJSON records."""
    import csv
    import io

    # Read response text and parse as CSV
    text = response.text
    reader = csv.DictReader(io.StringIO(text))

    for row in reader:
        yield row

def parse_ndjson_response(response) -> Iterator[dict]:
    """Parse NDJSON response (one JSON object per line)."""
    for line in response.iter_lines(decode_unicode=True):
        if line.strip():
            yield json.loads(line)
```

### CLI Arguments
```python
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="HTTP protocol plugin")
    parser.add_argument('url', nargs='?', help='URL to fetch')
    parser.add_argument('--method', default='GET', help='HTTP method')
    parser.add_argument('--headers', type=json.loads, help='HTTP headers (JSON)')
    parser.add_argument('--params', type=json.loads, help='Query parameters (JSON)')
    parser.add_argument('--data', help='Request body')
    parser.add_argument('--auth', help='Basic auth (username:password)')
    parser.add_argument('--timeout', type=int, default=30, help='Timeout in seconds')
    parser.add_argument('--format', choices=['json', 'csv', 'ndjson', 'raw', 'text'])
    parser.add_argument('--raw', action='store_true', help='Output raw response')
    parser.add_argument('--no-verify-ssl', dest='verify_ssl', action='store_false')

    args = parser.parse_args()

    # Build config
    config = {
        'url': args.url,
        'method': args.method,
        'timeout': args.timeout,
        'verify_ssl': args.verify_ssl,
    }

    if args.headers:
        config['headers'] = args.headers
    if args.params:
        config['params'] = args.params
    if args.data:
        config['data'] = args.data
    if args.auth:
        config['auth'] = args.auth
    if args.format:
        config['format'] = args.format
    if args.raw:
        config['format'] = 'raw'

    for record in reads(config):
        print(json.dumps(record), flush=True)
```

## Error Handling

### HTTP Errors
```python
try:
    response.raise_for_status()
except requests.HTTPError as e:
    print(f"HTTP Error {e.response.status_code}: {e.response.text}", file=sys.stderr)
    sys.exit(1)
```

### Timeout Handling
```python
try:
    response = requests.get(url, timeout=timeout)
except requests.Timeout:
    print(f"Request timeout after {timeout}s", file=sys.stderr)
    sys.exit(1)
```

### SSL Errors
```python
try:
    response = requests.get(url, verify=verify_ssl)
except requests.SSLError as e:
    print(f"SSL verification failed: {e}", file=sys.stderr)
    print("Use --no-verify-ssl to disable verification (not recommended)", file=sys.stderr)
    sys.exit(1)
```

## Testing Strategy

### Unit Tests
```python
def test_http_json_fetch(invoke):
    """Test fetching JSON from HTTP endpoint."""
    # Mock HTTP response
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'https://api.example.com/data.json',
                json={"name": "Alice", "age": 30}, status=200)

        res = invoke(['cat', 'https://api.example.com/data.json'])
        assert res.exit_code == 0
        records = [json.loads(line) for line in res.output.strip().split('\n')]
        assert len(records) == 1
        assert records[0]['name'] == 'Alice'

def test_http_json_array(invoke):
    """Test fetching JSON array - should yield one record per element."""
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'https://api.example.com/users.json',
                json=[{"name": "Alice"}, {"name": "Bob"}], status=200)

        res = invoke(['cat', 'https://api.example.com/users.json'])
        records = [json.loads(line) for line in res.output.strip().split('\n')]
        assert len(records) == 2
        assert records[0]['name'] == 'Alice'
        assert records[1]['name'] == 'Bob'
```

## Performance Considerations

1. **Streaming**: Use `response.iter_lines()` for large responses
2. **Chunked transfer**: Process response in chunks, don't buffer entire response
3. **Connection pooling**: Reuse HTTP connections when fetching multiple URLs
4. **Timeout defaults**: Reasonable 30s default to prevent hanging

## Future Enhancements

1. **Retry logic** with exponential backoff
2. **Rate limiting** support
3. **OAuth 2.0** authentication
4. **Pagination** handling (cursor, offset, page-based)
5. **GraphQL** query support
6. **WebSocket** streaming
7. **HTTP/2** support

## Integration with Profile System

This plugin integrates with REST API profiles (see rest-api-profile-design.md):

```bash
# Use HTTP plugin with API profile
jn cat @github/repos/anthropics/claude-code/issues
# Resolves to: https://api.github.com/repos/anthropics/claude-code/issues
# Uses profile's auth headers and base URL
```
