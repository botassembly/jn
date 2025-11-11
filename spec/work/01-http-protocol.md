# HTTP Protocol Plugin

## What
HTTP/HTTPS protocol plugin for fetching and posting data to web endpoints.

## Why
Foundation for remote data access, APIs, and downloading files from the web. Most common protocol for data integration.

## Key Features
- GET requests for fetching data
- POST requests for sending data
- Header support (Authorization, Content-Type, etc.)
- Streaming (constant memory for large downloads)
- Error handling for HTTP status codes

## Dependencies
- `curl` command (use existing tool, don't reimplement)

## Examples
```bash
# Fetch from URL
jn cat https://api.example.com/data.json | jn filter '.active == true'

# Download and process
jn cat https://example.com/data.xlsx | jn put local.csv

# POST data
jn cat local.json | jn put https://httpbin.org/post
```

## Test Resources
- HTTPBin: `https://httpbin.org/get`, `https://httpbin.org/post`
