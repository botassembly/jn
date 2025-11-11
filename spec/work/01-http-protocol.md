# HTTP Protocol Plugin

## Overview
Implement a basic HTTP protocol plugin that can fetch data from HTTP/HTTPS endpoints using GET and POST methods. This plugin will serve as the foundation for more complex protocol plugins (S3, APIs) and enable fetching remote data sources.

## Goals
- Support HTTP GET requests to fetch data from URLs
- Support HTTP POST requests to send data to endpoints
- Stream response data as NDJSON output
- Handle common HTTP headers (Authorization, Content-Type, etc.)
- Support basic authentication patterns
- Provide clear error messages for HTTP errors (4xx, 5xx)

## Resources
**Test URLs (HTTPBin):**
- `https://httpbin.org/get` - Test GET requests
- `https://httpbin.org/post` - Test POST requests
- `https://httpbin.org/status/200` - Test status codes
- `https://httpbin.org/headers` - Test header handling

**Public XLSX over HTTPS (for testing):**
- Wall Street Prep samples: `https://s3.amazonaws.com/wsp_sample_file/excel-templates/financial-statement-model-sample.xlsx`
- CMS Web Interface: `https://qpp-cm-prod-content.s3.amazonaws.com/uploads/1668/2021%20CMS%20Web%20Interface%20Excel%20Template%20with%20Sample%20Data.xlsx`

## Dependencies
- Use `curl` command (already available in most systems)
- Alternative: Python `urllib` or `requests` library if needed
- DO NOT implement custom HTTP client - leverage existing tools

## Technical Approach
- Implement `reads()` function to fetch from HTTP URLs
- Implement `writes()` function to POST data to endpoints
- Pattern matching: `^https?://.*` to detect HTTP/HTTPS URLs
- Parse response based on Content-Type header
- Stream response body (don't buffer entire response in memory)
- Support stdin for POST body data

## Usage Examples
```bash
# GET request
jn cat https://httpbin.org/get | jn put response.json

# POST request
jn cat data.json | jn put https://httpbin.org/post

# With headers (future: via CLI args)
jn cat https://api.example.com/data --header "Authorization: Bearer TOKEN"
```

## Out of Scope
- Complex authentication (OAuth, JWT) - save for profiles
- Retry logic and exponential backoff - add later
- Request rate limiting - add later
- WebSocket support - different protocol
- Cookie handling - add later if needed
- SSL certificate validation options - use defaults
- HTTP/2 or HTTP/3 - rely on curl defaults
- Proxy configuration - add later if needed

## Success Criteria
- Can fetch data from HTTPBin test endpoints
- Can download XLSX files over HTTPS
- Properly handles HTTP error codes
- Streams response data (constant memory usage)
- Works in pipeline: `jn cat URL | jn filter ...`
