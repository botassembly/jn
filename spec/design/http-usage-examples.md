# HTTP Plugin & REST API Profiles - Usage Patterns

Quick reference for common HTTP and profile usage patterns.

## Basic HTTP Fetch

```bash
# Fetch and display JSON
jn cat https://opencode.ai/config.json

# Fetch CSV, filter, export
jn cat https://example.com/data.csv | jn filter '.revenue > 1000' | jn put filtered.json

# Convert formats
jn cat https://example.com/data.json | jn put output.yaml
```

## Authentication

```bash
# Bearer token (from environment)
jn cat https://api.example.com/data \
  --headers '{"Authorization": "Bearer ${API_TOKEN}"}'

# Basic auth
jn cat https://api.example.com/secure --auth "user:pass"

# API key in header
jn cat https://api.example.com/data \
  --headers '{"X-API-Key": "${API_KEY}"}'
```

## HTTP Methods

```bash
# POST with JSON body
echo '{"query": "test"}' | \
  jn cat https://api.example.com/search --method POST

# PUT to update
echo '{"status": "active"}' | \
  jn cat https://api.example.com/users/123 --method PUT

# DELETE
jn cat https://api.example.com/users/123 --method DELETE
```

## Profile Usage

### Setup Profile
Create `~/.local/jn/profiles/http/github.json`:
```json
{
  "base_url": "https://api.github.com",
  "headers": {
    "Authorization": "Bearer ${GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
  }
}
```

### Use Profile
```bash
# Path-based access
jn cat @github/repos/microsoft/vscode/issues

# With path variables
jn cat @github/users/octocat/repos

# Search with query params
jn cat '@github/search/repositories?q=language:python&sort=stars'
```

## Real-World Patterns

### OpenCode.ai Config Analysis
```bash
# Fetch and analyze
jn cat https://opencode.ai/config.json | \
  jn filter '.features | to_entries | .[] | select(.value)' | \
  jn put enabled-features.csv
```

### RESTful API Dev Workflow
Setup profile `~/.local/jn/profiles/http/restful-api.json`:
```json
{
  "base_url": "https://api.restful-api.dev",
  "paths": {
    "objects": "/objects",
    "object": "/objects/{id}"
  }
}
```

```bash
# List all objects
jn cat @restful-api/objects

# Get specific object
jn cat @restful-api/objects/3

# Filter by price
jn cat @restful-api/objects | \
  jn filter '.[] | select(.data.price != null) | {name, price: .data.price}'

# Price statistics
jn cat @restful-api/objects | \
  jn filter '@builtin/stats' --field data.price

# Create new object
echo '{"name":"iPhone 15","data":{"price":999}}' | \
  jn cat @restful-api/objects --method POST
```

### GitHub API Integration
```bash
# List user repos
jn cat @github/users/octocat/repos | \
  jn filter '.[] | {name, stars: .stargazers_count}' | \
  jn put repos.csv

# Get open issues
jn cat @github/repos/microsoft/vscode/issues | \
  jn filter '.[] | select(.state == "open")' | \
  jn filter '@builtin/group_count' --by labels
```

## Multi-API Pipelines

```bash
# Fetch from multiple APIs
jn cat @api1/data @api2/data | \
  jn filter '@builtin/flatten_nested' | \
  jn put merged.csv

# API to database
jn cat @source-api/daily-data | \
  jn filter '@analytics/transform' | \
  jn put @postgres/metrics_table
```

## Performance Patterns

### Streaming Large Files
```bash
# Process first 100 records, stop download
jn cat https://example.com/huge-dataset.csv | head -n 100

# Constant memory regardless of file size
jn cat https://example.com/10gb-file.csv | \
  jn filter '.revenue > 1000' | \
  jn put filtered.csv
```

### Parallel Fetches
```bash
# Fetch multiple URLs in parallel
cat urls.txt | xargs -P 4 -I {} jn cat {}

# Example urls.txt:
# @api/users/1
# @api/users/2
# @api/users/3
```

### Caching Responses
```bash
# Cache expensive query
jn cat @api/expensive-query | tee cache.jsonl | jn filter '...'

# Next time: read from cache
jn cat cache.jsonl | jn filter '...'
```

## Error Handling

### Timeout Control
```bash
# Custom timeout (default 30s)
jn cat @slow-api/endpoint --timeout 60
```

### SSL Issues
```bash
# Disable SSL verification (dev/testing only)
jn cat https://self-signed.example.com/ --no-verify-ssl
```

### Format Override
```bash
# Force JSON parsing
jn cat https://example.com/data.txt --format json
```

## Pagination Patterns

### Manual Pagination
```bash
# Loop through pages
for page in {1..10}; do
  jn cat "@api/data?page=$page&limit=100"
done | jn put all-pages.json
```

### Cursor-Based
```bash
# Follow cursor links (manual)
cursor=""
while true; do
  response=$(jn cat "@api/data?cursor=$cursor")
  echo "$response" | jn filter '.items[]'
  cursor=$(echo "$response" | jn filter '.next_cursor // empty' -r)
  [[ -z "$cursor" ]] && break
done
```

## Monitoring & Alerting

```bash
# Poll API every 30 seconds
while true; do
  jn cat @api/status | \
    jn filter ". + {timestamp: now}" | \
    jn put --append monitoring.jsonl
  sleep 30
done

# Alert on condition
jn cat @api/metrics | \
  jn filter 'select(.error_rate > 5) | {alert: "High error rate", rate}' | \
  jn put --append alerts.log
```

## Best Practices

1. **Use environment variables for secrets** - Never hardcode tokens
2. **Create profiles for frequent APIs** - Reduce repetition
3. **Profile hierarchy** - Project profiles for team, user for personal
4. **Stream large datasets** - Don't buffer entire responses
5. **Handle rate limits** - Add delays between requests if needed
6. **Cache expensive queries** - Save responses locally
7. **Validate profiles** - Use `jn profile validate` before use

## Troubleshooting

```bash
# Test profile connection
jn profile test github

# Show resolved URL (dry-run)
jn cat @api/endpoint --dry-run

# Verbose output
jn cat @api/data --verbose 2>&1 | tee debug.log
```

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `401 Unauthorized` | Invalid/missing token | Check `${TOKEN}` env var |
| `403 Forbidden` | Insufficient permissions | Verify API key scopes |
| `404 Not Found` | Wrong URL/endpoint | Check profile base_url |
| `429 Too Many Requests` | Rate limited | Add delays between requests |
| `Profile not found` | Typo or missing file | Check `~/.local/jn/profiles/http/` |
| `Environment variable not set` | Missing `${VAR}` | Export variable: `export API_KEY=...` |

## See Also

- [HTTP Plugin Design](http-plugin-design.md) - Architecture and decisions
- [REST API Profile Design](rest-api-profile-design.md) - Profile system details
