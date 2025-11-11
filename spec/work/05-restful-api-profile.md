# RESTful API Dev Profile (HTTP Profile Example)

## Overview
Create an HTTP profile for the RESTful API Dev service (https://restful-api.dev), a free public API for testing CRUD operations. This demonstrates how HTTP profiles work with connection config, path templates, and parameter handling.

## Goals
- Create example HTTP profile configuration
- Demonstrate path-based resource access (`@restful/objects`)
- Show parameter passing for queries
- Implement both reads (GET) and writes (POST/PUT/DELETE)
- Serve as template for other HTTP API profiles (GitHub, Stripe, etc.)

## Resources
**API Documentation:** https://restful-api.dev

**Endpoints:**
- `GET /objects` - List all objects
- `GET /objects/{id}` - Get specific object
- `POST /objects` - Create new object
- `PUT /objects/{id}` - Update object
- `DELETE /objects/{id}` - Delete object

**Sample data:**
```json
{
  "name": "Apple MacBook Pro 16",
  "data": {
    "year": 2019,
    "price": 1849.99,
    "CPU model": "Intel Core i9",
    "Hard disk size": "1 TB"
  }
}
```

## Profile Structure

**Location:** `profiles/http/restful-api-dev.json`

**Configuration:**
```json
{
  "base_url": "https://api.restful-api.dev",
  "headers": {
    "Content-Type": "application/json",
    "Accept": "application/json"
  },
  "timeout": 30,
  "rate_limit": {
    "requests_per_second": 10
  }
}
```

**Note:** No authentication required (public API).

## Usage Examples

```bash
# List all objects
jn cat @restful-api-dev/objects | jn put all-objects.json

# Get specific object
jn cat @restful-api-dev/objects/3 | jn put object-3.json

# Create new object
echo '{"name": "Test Device", "data": {"year": 2024}}' | jn put @restful-api-dev/objects

# Filter objects
jn cat @restful-api-dev/objects | jn filter '.data.year > 2020' | jn put recent.json

# Query with parameters (if supported)
jn cat @restful-api-dev/objects?year=2019 | jn put filtered.json
```

## Technical Requirements

### Profile Resolution
1. Detect `@restful-api-dev/path` pattern
2. Load config from `profiles/http/restful-api-dev.json`
3. Append `/path` to `base_url`
4. Merge profile headers with request headers
5. Pass to HTTP plugin for execution

### HTTP Plugin Integration
HTTP plugin needs to:
- Accept profile config as parameter
- Build full URL: `base_url + path`
- Add headers from profile
- Support GET (reads) and POST/PUT (writes)
- Handle JSON request/response bodies

### Parameter Handling
Support multiple parameter styles:
- Path parameters: `@restful-api-dev/objects/3` → `/objects/3`
- Query parameters: `@restful-api-dev/objects?id=3` → `/objects?id=3`
- CLI args: `--param year=2019` → `/objects?year=2019`

## Out of Scope
- Authentication patterns (OAuth, API keys) - this is public API
- Pagination handling - just return raw response
- Rate limiting enforcement - just document limits
- Retry logic - add later
- Response caching - add later
- GraphQL support - different API style
- WebSocket connections - different protocol
- File upload/download - use direct HTTP for now
- Custom HTTP methods (PATCH, HEAD) - add later

## Success Criteria
- Profile config loads correctly
- Can list all objects from API
- Can get specific object by ID
- Can create new object via POST
- Path resolution works: `@restful-api-dev/objects` → `https://api.restful-api.dev/objects`
- Headers from profile applied correctly
- Works in pipelines with filters
- Can be used as template for other HTTP APIs

## Future Extensions
Once this works, create similar profiles for:
- GitHub API (with authentication)
- Stripe API (with API keys)
- Internal company APIs
- Other public APIs (OpenWeatherMap, etc.)
