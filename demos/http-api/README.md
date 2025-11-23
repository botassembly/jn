# HTTP API Demo

This demo shows how to fetch data from HTTP/REST APIs using JN's universal addressing system.

## What You'll Learn

- Fetching data from REST APIs
- Using format hints for JSON/CSV/YAML APIs
- Handling compressed responses (.gz)
- Creating HTTP profiles for authenticated APIs
- Combining API data with local files

## Basic HTTP Fetching

### Fetch JSON from URL

```bash
# Explicit format hint
jn cat "https://api.github.com/users/octocat~json"

# Auto-detect from Content-Type header
jn cat "https://api.github.com/users/octocat"
```

### Fetch and Filter

```bash
jn cat "https://api.github.com/users/octocat~json" | \
  jn filter '{name: .name, repos: .public_repos, location: .location}'
```

### Fetch and Save

```bash
# Save as JSON
jn cat "https://api.github.com/users/octocat~json" | \
  jn put user.json

# Save as CSV
jn cat "https://api.github.com/users/octocat~json" | \
  jn put user.csv

# Save as YAML
jn cat "https://api.github.com/users/octocat~json" | \
  jn put user.yaml
```

## Public API Examples

### GitHub API

```bash
# Get user info
jn cat "https://api.github.com/users/torvalds~json"

# Get user's repositories
jn cat "https://api.github.com/users/torvalds/repos~json" | \
  jn filter '{name: .name, stars: .stargazers_count, language: .language}' | \
  jn put repos.json
```

### JSONPlaceholder (Test API)

```bash
# Get posts
jn cat "https://jsonplaceholder.typicode.com/posts~json" | jn head -n 5

# Get specific post
jn cat "https://jsonplaceholder.typicode.com/posts/1~json"

# Get users
jn cat "https://jsonplaceholder.typicode.com/users~json" | \
  jn filter '{name: .name, email: .email, city: .address.city}'
```

### REST Countries API

```bash
# Get all countries
jn cat "https://restcountries.com/v3.1/all~json" | jn head -n 5

# Get specific country
jn cat "https://restcountries.com/v3.1/name/france~json" | \
  jn filter '{
    name: .name.common,
    capital: .capital[0],
    population: .population,
    region: .region
  }'

# Find European countries
jn cat "https://restcountries.com/v3.1/region/europe~json" | \
  jn filter '{name: .name.common, capital: .capital[0]}' | \
  jn put european_countries.csv
```

### Cat Facts API

```bash
# Get random cat fact
jn cat "https://catfact.ninja/fact~json"

# Get multiple cat facts
jn cat "https://catfact.ninja/facts?limit=10~json" | \
  jn filter '.data[]' | \
  jn filter '{fact: .fact, length: .length}'
```

## HTTP Profiles

For APIs requiring authentication or custom headers, create HTTP profiles.

### Creating a Profile

Create `.jn/profiles/http/myapi/_meta.json`:

```json
{
  "base_url": "https://api.example.com",
  "headers": {
    "Authorization": "Bearer ${MY_API_TOKEN}",
    "Accept": "application/json"
  },
  "timeout": 30
}
```

Create `.jn/profiles/http/myapi/users.json`:

```json
{
  "path": "/users",
  "method": "GET",
  "type": "source",
  "params": ["limit", "page"],
  "description": "Get users list"
}
```

### Using the Profile

```bash
export MY_API_TOKEN="your-token-here"
jn cat "@myapi/users?limit=10"
```

## Compressed Responses

JN automatically handles gzip compression:

```bash
# Auto-detects .gz extension
jn cat "https://example.com/data.json.gz"

# Or explicitly with format hint
jn cat "https://example.com/data.gz~json"
```

## Pipeline Examples

### Fetch → Filter → Save

```bash
jn cat "https://api.github.com/users/octocat/repos~json" | \
  jn filter '.stargazers_count > 100' | \
  jn filter '{name: .name, stars: .stargazers_count, url: .html_url}' | \
  jn put popular_repos.json
```

### Combine Multiple APIs

```bash
# Get user info
jn cat "https://api.github.com/users/torvalds~json" | \
  jn filter '{user: .login, name: .name}' > user_info.ndjson

# Get user's repos
jn cat "https://api.github.com/users/torvalds/repos~json" | \
  jn filter '{repo: .name, stars: .stargazers_count}' > user_repos.ndjson
```

### Fetch and Aggregate

```bash
# Get posts and count by user
jn cat "https://jsonplaceholder.typicode.com/posts~json" | \
  jq -s 'group_by(.userId) | map({
    userId: .[0].userId,
    post_count: length
  }) | .[]'
```

## Run the Examples

Execute the provided script:

```bash
./run_examples.sh
```

This will:
- Fetch data from several public APIs
- Demonstrate filtering and transformation
- Create example output files

## Key Features

### Universal Addressing

```
https://domain.com/path[~format][?params]
```

- **Protocol**: `http://` or `https://`
- **Format hint**: `~json`, `~csv`, `~yaml` (optional)
- **Query params**: Standard URL query string

### Auto-detection

JN automatically detects:
- Content-Type from HTTP headers
- Compression from file extensions (.gz)
- Format from file extensions (.json, .csv)

### Format Hints

Override auto-detection with explicit format:
- `~json` - JSON response
- `~csv` - CSV response
- `~yaml` - YAML response
- `~ndjson` - Newline-delimited JSON

## Error Handling

HTTP errors are returned as NDJSON error records:

```json
{
  "_error": true,
  "type": "http_error",
  "status": 404,
  "message": "Not Found"
}
```

## Next Steps

- See the GenomOncology demo for a complete HTTP profile example
- Check the MCP demo for protocol integration
- Explore the CSV demo for data transformation techniques
