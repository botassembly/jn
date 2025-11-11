# HTTP Plugin & REST API Profiles - Usage Examples

## Real-World Examples

### Example 1: OpenCode.ai Config Processing

**Scenario:** Fetch and process OpenCode.ai configuration file

```bash
# Simple fetch and display
jn cat https://opencode.ai/config.json | jq .

# Convert to YAML for easier reading
jn cat https://opencode.ai/config.json | jn put config.yaml

# Extract specific fields
jn cat https://opencode.ai/config.json | \
  jn filter '{
    version: .version,
    features: .features | keys,
    theme: .theme.default
  }'

# List all enabled features
jn cat https://opencode.ai/config.json | \
  jn filter '.features | to_entries | .[] | select(.value == true) | .key'

# Export to CSV
jn cat https://opencode.ai/config.json | \
  jn filter '.features | to_entries | .[] | {feature: .key, enabled: .value}' | \
  jn put features.csv
```

**With Profile:**

Create `~/.local/jn/profiles/http/opencode.json`:
```json
{
  "base_url": "https://opencode.ai",
  "description": "OpenCode.ai - Open source code intelligence",
  "paths": {
    "config": "/config.json",
    "api": "/api",
    "docs": "/docs"
  }
}
```

Usage:
```bash
# Cleaner syntax
jn cat @opencode/config.json

# Get and analyze
jn cat @opencode/config.json | \
  jn filter '@builtin/flatten_nested' | \
  jn put opencode-analysis.csv
```

---

### Example 2: RESTful API Dev - Complete Workflow

**Profile:** `~/.local/jn/profiles/http/restful-api.json`
```json
{
  "base_url": "https://api.restful-api.dev",
  "description": "RESTful API Dev - Sample REST API for device data",
  "headers": {
    "Content-Type": "application/json"
  },
  "paths": {
    "objects": "/objects",
    "object": "/objects/{id}"
  },
  "methods": {
    "list_all": {
      "path": "/objects",
      "method": "GET",
      "description": "Get all objects"
    },
    "get_by_id": {
      "path": "/objects/{id}",
      "method": "GET",
      "description": "Get single object by ID"
    },
    "create": {
      "path": "/objects",
      "method": "POST",
      "description": "Create new object"
    },
    "update": {
      "path": "/objects/{id}",
      "method": "PUT",
      "description": "Update existing object"
    },
    "delete": {
      "path": "/objects/{id}",
      "method": "DELETE",
      "description": "Delete object"
    }
  }
}
```

#### List All Devices
```bash
# Fetch all objects
jn cat @restful-api/objects

# Get specific fields
jn cat @restful-api/objects | \
  jn filter '.[] | {id: .id, name: .name}'

# Filter by criteria
jn cat @restful-api/objects | \
  jn filter '.[] | select(.data != null and .data.price != null)'

# Export to CSV
jn cat @restful-api/objects | jn put devices.csv
```

#### Get Specific Device
```bash
# Get device with ID 3
jn cat @restful-api/objects/3

# Get and extract specific data
jn cat @restful-api/objects/3 | \
  jn filter '{
    device: .name,
    year: .data.year,
    price: .data.price,
    cpu: .data["CPU model"]
  }'
```

#### Create New Device
```bash
# Create new object
echo '{
  "name": "Apple MacBook Pro 16",
  "data": {
    "year": 2023,
    "price": 2499.99,
    "CPU model": "Apple M3 Pro",
    "Hard disk size": "1 TB SSD"
  }
}' | jn http @restful-api/objects --method POST

# Or from file
jn cat new-device.json | \
  jn http @restful-api/objects --method POST | \
  jn put created-device.json
```

#### Update Existing Device
```bash
# Update device 3
echo '{
  "name": "Updated Name",
  "data": {
    "price": 1999.99
  }
}' | jn http @restful-api/objects/3 --method PUT
```

#### Analytics Pipeline
```bash
# Get all devices, analyze pricing
jn cat @restful-api/objects | \
  jn filter '@builtin/stats' --field data.price

# Group by year
jn cat @restful-api/objects | \
  jn filter '.[] | select(.data.year != null)' | \
  jn filter '@builtin/group_count' --by data.year | \
  jn put devices-by-year.csv

# Price analysis
jn cat @restful-api/objects | \
  jn filter '.[] | select(.data.price != null) | {
    name: .name,
    price: .data.price,
    year: .data.year
  }' | \
  jn filter '@builtin/group_sum' --by year --sum price
```

---

### Example 3: GitHub API Integration

**Profile:** `~/.local/jn/profiles/http/github.json`
```json
{
  "base_url": "https://api.github.com",
  "description": "GitHub REST API v3",
  "headers": {
    "Accept": "application/vnd.github+json",
    "Authorization": "Bearer ${GITHUB_TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28"
  },
  "rate_limit": {
    "requests_per_minute": 60
  },
  "paths": {
    "user": "/user",
    "repos": "/repos/{owner}/{repo}",
    "issues": "/repos/{owner}/{repo}/issues",
    "pulls": "/repos/{owner}/{repo}/pulls"
  }
}
```

**Setup:**
```bash
# Set GitHub token
export GITHUB_TOKEN="ghp_your_token_here"
```

**Usage:**
```bash
# Get your user info
jn cat @github/user

# List repos for a user
jn cat @github/users/octocat/repos | \
  jn filter '.[] | {name: .name, stars: .stargazers_count}' | \
  jn put octocat-repos.csv

# Get repo issues
jn cat @github/repos/microsoft/vscode/issues | \
  jn filter '.[] | select(.state == "open") | {
    number: .number,
    title: .title,
    labels: [.labels[].name]
  }'

# Search repositories
jn cat '@github/search/repositories?q=language:python+stars:>1000&sort=stars' | \
  jn filter '.items[] | {name: .full_name, stars: .stargazers_count}' | \
  jn filter '@builtin/stats' --field stars
```

---

### Example 4: Multi-API Data Pipeline

**Scenario:** Aggregate data from multiple APIs

```bash
# Fetch from multiple sources
cat sources.txt
# @restful-api/objects
# @github/repos/microsoft/vscode
# https://api.example.com/data.json

# Process each source
cat sources.txt | while read source; do
  jn cat "$source" | jn filter '.id = "'"$source"'"'
done | jn filter '@builtin/group_count' --by source
```

**Complex Pipeline:**
```bash
# 1. Fetch from API
jn cat @restful-api/objects | \

# 2. Filter and transform
jn filter '.[] | select(.data.price != null) | {
  name: .name,
  price: .data.price,
  year: .data.year // 2024
}' | \

# 3. Calculate statistics
jn filter '@builtin/stats' --field price | \

# 4. Save results
jn put analysis.json
```

---

### Example 5: HTTP Methods Beyond GET

#### POST - Create Resource
```bash
# JSON payload
echo '{"name": "Test", "value": 42}' | \
  jn cat @api/resources --method POST

# From file
jn cat data.json | jn cat @api/resources --method POST
```

#### PUT - Update Resource
```bash
echo '{"value": 100}' | \
  jn cat @api/resources/123 --method PUT
```

#### DELETE - Remove Resource
```bash
jn cat @api/resources/123 --method DELETE
```

#### Custom Headers
```bash
jn cat @api/data \
  --headers '{"X-Custom-Header": "value", "X-Request-ID": "abc123"}'
```

---

### Example 6: Error Handling & Debugging

#### Verbose Mode
```bash
# Show HTTP headers and status
jn cat https://api.example.com/data --verbose

# Show full request/response
jn cat @api/endpoint --debug
```

#### Timeout Configuration
```bash
# Custom timeout (default 30s)
jn cat @slow-api/endpoint --timeout 60
```

#### SSL/TLS Issues
```bash
# Disable SSL verification (not recommended for production)
jn cat https://self-signed.badssl.com/ --no-verify-ssl
```

#### Retry Logic
```bash
# Retry failed requests
jn cat @unreliable-api/data --retry 3 --retry-delay 2
```

---

### Example 7: Authentication Methods

#### Bearer Token
```json
{
  "headers": {
    "Authorization": "Bearer ${API_TOKEN}"
  }
}
```

#### Basic Auth
```bash
jn cat @api/secure --auth "username:password"
```

#### API Key in Header
```json
{
  "headers": {
    "X-API-Key": "${API_KEY}"
  }
}
```

#### API Key in Query Parameter
```bash
jn cat '@api/data?api_key=${API_KEY}'
```

---

### Example 8: Response Processing

#### JSON Array Responses
```bash
# Input: [{"id": 1}, {"id": 2}]
# Output: Two NDJSON records
jn cat @api/array-endpoint
# {"id": 1}
# {"id": 2}
```

#### Nested JSON
```bash
# Flatten nested structure
jn cat @api/nested | jn filter '@builtin/flatten_nested'
```

#### CSV Responses
```bash
# Automatically detected and parsed
jn cat https://example.com/data.csv
# Outputs NDJSON records, one per CSV row
```

#### Large Responses
```bash
# Stream large responses (constant memory)
jn cat @api/huge-dataset | head -n 100
# Processes only first 100 records, stops download
```

---

### Example 9: Pagination Handling

#### Manual Pagination
```bash
# Page through results
for page in {1..5}; do
  jn cat "@api/data?page=$page&limit=100"
done | jn put all-pages.json
```

#### Cursor-based Pagination
```bash
# Follow next_cursor links
cursor=""
while true; do
  response=$(jn cat "@api/data?cursor=$cursor")
  echo "$response" | jn filter '.items[]'
  cursor=$(echo "$response" | jn filter '.next_cursor // empty')
  [[ -z "$cursor" ]] && break
done
```

---

### Example 10: Real-time Data Monitoring

#### Poll API Periodically
```bash
# Monitor API every 30 seconds
while true; do
  timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  jn cat @api/status | jn filter ". + {timestamp: \"$timestamp\"}" | \
    jn put --append monitoring.jsonl
  sleep 30
done
```

#### Alert on Condition
```bash
# Alert if error rate > 5%
jn cat @api/metrics | \
  jn filter 'select(.error_rate > 5) | {
    alert: "High error rate",
    rate: .error_rate,
    timestamp: now | strftime("%Y-%m-%d %H:%M:%S")
  }' | \
  jn put --append alerts.log
```

---

## Performance Tips

1. **Use streaming for large datasets** - JN processes line-by-line with constant memory
2. **Filter early** - Apply `jn filter` immediately after fetch to reduce data
3. **Profile reuse** - Store common API configs in profiles
4. **Parallel fetches** - Use xargs or parallel for multiple URLs
5. **Cache responses** - Save fetched data locally to avoid repeated API calls

```bash
# Parallel fetches
cat urls.txt | xargs -P 4 -I {} jn cat {}

# Cache response
jn cat @api/expensive-query | tee cache.jsonl | jn filter '...'
# Next time: jn cat cache.jsonl | jn filter '...'
```

---

## Troubleshooting

### Common Issues

1. **401 Unauthorized** - Check API token/credentials
2. **403 Forbidden** - Check API permissions or rate limits
3. **404 Not Found** - Verify URL/endpoint path
4. **429 Too Many Requests** - Rate limited, slow down requests
5. **500 Server Error** - API issue, retry later or contact support

### Debug Commands
```bash
# Test profile
jn profile test github

# Validate profile syntax
jn profile validate myapi

# Show resolved URL
jn cat @api/endpoint --dry-run

# Verbose output
jn cat @api/data --verbose 2>&1 | tee debug.log
```

---

## Best Practices

1. **Use environment variables for secrets** - Never hardcode API keys
2. **Create profiles for frequently used APIs** - DRY principle
3. **Add descriptions to profiles** - Document what each profile does
4. **Version control profiles** - Commit to `.jn/profiles/` in your project
5. **Handle rate limits** - Respect API rate limits, add delays if needed
6. **Validate responses** - Check for expected fields before processing
7. **Log errors** - Save error responses for debugging
8. **Test in development** - Use test/sandbox API endpoints first

---

## Integration with Other JN Features

### Combine with JQ Profiles
```bash
jn cat @api/data | \
  jn filter '@analytics/transform' | \
  jn filter '@builtin/stats' --field revenue
```

### Chain with Format Plugins
```bash
jn cat @api/report.csv | \
  jn filter '.revenue > 1000' | \
  jn put summary.xlsx
```

### Use with Databases
```bash
# API → Database
jn cat @api/daily-data | \
  jn put @postgres/metrics_table

# Database → API
jn cat @postgres/users | \
  jn http @notification-api/send --method POST
```
