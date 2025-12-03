# Profile System

> **Purpose**: How profiles configure and simplify data access.

---

## What Is a Profile?

A profile is a reusable configuration for accessing data sources. Instead of:

```bash
curl -H "Authorization: Bearer $TOKEN" \
     -H "Accept: application/json" \
     "https://api.example.com/v2/users?limit=100"
```

You write:

```bash
jn cat @myapi/users?limit=100
```

Profiles store:
- Connection details (URLs, auth)
- Default parameters
- Request configuration

---

## Profile Types

### HTTP Profiles

Configure REST API endpoints:

```json
{
  "base_url": "https://api.example.com/v2",
  "headers": {
    "Authorization": "Bearer ${API_TOKEN}",
    "Accept": "application/json"
  },
  "timeout": 30
}
```

### ZQ Profiles

Store reusable filter expressions:

```zq
# Filter: active users by region
# Parameters: region
select(.status == "active" and .region == $region)
| pick(.id, .name, .email)
```

### Database Profiles

Configure database connections:

```json
{
  "connection": "postgresql://user:${DB_PASS}@host:5432/mydb",
  "default_schema": "public",
  "query_timeout": 60
}
```

### Protocol-Specific Profiles

Gmail, MCP, and other protocols have specialized profiles:

```json
{
  "credentials_path": "~/.config/jn/gmail-credentials.json",
  "default_labels": ["INBOX"],
  "max_results": 100
}
```

---

## Profile Hierarchy

Profiles support hierarchical configuration through `_meta.json` files.

### Directory Structure

```
profiles/http/myapi/
├── _meta.json          # Base config (shared by all endpoints)
├── users.json          # GET /users endpoint
├── projects.json       # GET /projects endpoint
└── orders/
    ├── _meta.json      # Nested base (extends parent _meta)
    └── pending.json    # GET /orders/pending endpoint
```

### `_meta.json` (Base Configuration)

```json
{
  "base_url": "https://api.mycompany.com/v1",
  "headers": {
    "Authorization": "Bearer ${MYAPI_TOKEN}",
    "X-Client-Id": "jn-etl"
  },
  "timeout": 30,
  "retry": 3
}
```

### Endpoint Configuration

```json
{
  "path": "/users",
  "method": "GET",
  "params": {
    "limit": 100,
    "active": true
  },
  "description": "List all active users"
}
```

### Merge Semantics

When loading `@myapi/users`:

1. Load `profiles/http/myapi/_meta.json`
2. Load `profiles/http/myapi/users.json`
3. Deep merge: endpoint overrides base

Result:
```json
{
  "base_url": "https://api.mycompany.com/v1",
  "path": "/users",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer ${MYAPI_TOKEN}",
    "X-Client-Id": "jn-etl"
  },
  "params": {
    "limit": 100,
    "active": true
  },
  "timeout": 30,
  "retry": 3,
  "description": "List all active users"
}
```

---

## Profile Sources

Profiles are discovered from multiple locations:

### Priority Order

```
1. Project profiles    .jn/profiles/
2. User profiles       ~/.local/jn/profiles/
3. Plugin-bundled      (embedded in plugins)
4. Plugin-discovered   (dynamic discovery)
```

Higher priority sources override lower ones.

### Project Profiles

Project-specific configurations in `.jn/profiles/`:

```
myproject/
├── .jn/
│   └── profiles/
│       └── http/
│           └── internal-api/
│               ├── _meta.json
│               └── reports.json
└── ...
```

### User Profiles

Personal configurations in `~/.local/jn/profiles/`:

```
~/.local/jn/profiles/
├── http/
│   ├── github/
│   │   ├── _meta.json
│   │   ├── repos.json
│   │   └── issues.json
│   └── mycompany/
│       └── ...
└── zq/
    └── filters/
        ├── active_only.zq
        └── recent.zq
```

### Plugin-Bundled Profiles

Plugins can include default profiles:

```
HTTP plugin bundles:
├── @github/repos
├── @github/issues
├── @jsonplaceholder/posts
└── @jsonplaceholder/users
```

### Dynamic Discovery

Plugins can discover profiles at runtime:

```bash
# DuckDB discovers tables as profiles
jn profile list --type=duckdb --database=sales.db
# @duckdb/customers
# @duckdb/orders
# @duckdb/products
```

---

## Environment Variable Substitution

Profiles support `${VAR}` syntax for secrets:

### Basic Substitution

```json
{
  "headers": {
    "Authorization": "Bearer ${API_TOKEN}"
  }
}
```

When loaded, `${API_TOKEN}` is replaced with the environment variable value.

### Default Values

```json
{
  "timeout": "${TIMEOUT:-30}"
}
```

If `TIMEOUT` is not set, uses `30`.

### Nested Substitution

Substitution works in nested structures:

```json
{
  "auth": {
    "username": "${DB_USER}",
    "password": "${DB_PASS}"
  }
}
```

### Security

- Resolved values are never logged
- Profiles can be shared without exposing secrets
- Environment variables set at runtime

---

## Profile Reference Syntax

Access profiles with `@namespace/name`:

### Basic Reference

```bash
jn cat @myapi/users
```

### With Parameters

```bash
jn cat "@myapi/users?limit=10&status=active"
```

Parameters are merged with profile defaults.

### Nested References

```bash
jn cat @myapi/orders/pending
```

Resolves to `profiles/http/myapi/orders/pending.json`.

---

## Profiles as Plugin Capability

Plugins can implement `--mode=profiles` to provide profile-like functionality:

### Profile Mode Interface

```bash
# List available profiles
plugin --mode=profiles --list

# Get profile details
plugin --mode=profiles --info=@namespace/name

# Discover profiles dynamically
plugin --mode=profiles --discover=<url>
```

### Example: DuckDB Plugin

```bash
# List tables as profiles
duckdb --mode=profiles --list --database=sales.db
```

Output:
```json
{"reference": "@duckdb/customers", "description": "Query customers table"}
{"reference": "@duckdb/orders", "description": "Query orders table"}
```

### Example: HTTP Plugin

```bash
# Discover API endpoints
http --mode=profiles --discover=https://api.example.com
```

Reads OpenAPI spec, creates profile definitions.

---

## HTTP Profile Details

HTTP profiles have specific fields:

### Full Schema

```json
{
  "base_url": "https://api.example.com",
  "path": "/users",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer ${TOKEN}",
    "Accept": "application/json"
  },
  "params": {
    "limit": 100
  },
  "timeout": 30,
  "retry": 3,
  "retry_backoff": "exponential",
  "follow_redirects": true,
  "verify_ssl": true,
  "description": "List users",
  "response_format": "json"
}
```

### URL Construction

```
base_url + path + query_params
https://api.example.com/users?limit=100
```

### Authentication Types

**Bearer Token**:
```json
{
  "headers": {
    "Authorization": "Bearer ${TOKEN}"
  }
}
```

**Basic Auth**:
```json
{
  "auth": {
    "type": "basic",
    "username": "${USER}",
    "password": "${PASS}"
  }
}
```

**API Key**:
```json
{
  "headers": {
    "X-API-Key": "${API_KEY}"
  }
}
```

---

## ZQ Profile Details

ZQ profiles store filter expressions:

### File Format

```zq
# Description: Filter active users by region
# Parameters: region, min_age
select(.status == "active")
| select(.region == $region)
| select(.age >= $min_age)
| pick(.id, .name, .email, .region)
```

### Usage

```bash
jn cat users.csv | jn filter @filters/active_by_region?region=West&min_age=21
```

### Parameter Types

- **String**: Quoted in expression
- **Number**: Unquoted in expression
- **Boolean**: `true` or `false`

```
$region → "West"     (string)
$min_age → 21        (number)
$active → true       (boolean)
```

---

## Profile CLI

Manage profiles with `jn profile`:

### List Profiles

```bash
# All profiles
jn profile list

# By type
jn profile list --type=http

# Search
jn profile list --query=github
```

### Profile Info

```bash
jn profile info @myapi/users
```

Output:
```
Profile: @myapi/users
Type: http
Path: ~/.local/jn/profiles/http/myapi/users.json

URL: https://api.example.com/v1/users
Method: GET
Parameters:
  - limit (default: 100)
  - status (default: active)

Example:
  jn cat @myapi/users?limit=10
```

### Discover Profiles

```bash
jn profile discover https://api.example.com
```

Queries API for discoverable endpoints (OpenAPI, etc.).

---

## Design Decisions

### Why Hierarchical?

**Benefits**:
- Share common config (auth, base_url)
- Override per-endpoint
- Organize by service/namespace

**Trade-offs**:
- Merge semantics can be confusing
- Must understand inheritance

### Why Environment Variables?

**Benefits**:
- Secrets stay in environment
- Profiles can be version-controlled
- Different values per environment

**Trade-offs**:
- Must set variables before use
- No built-in secret management

### Why Profiles as Plugin Capability?

**Benefits**:
- Dynamic discovery (DuckDB tables, API endpoints)
- Plugins own their domain knowledge
- Unified interface

**Trade-offs**:
- More complex plugin interface
- Discovery may be slow

---

## See Also

- [06-matching-resolution.md](06-matching-resolution.md) - Profile resolution flow
- [05-plugin-system.md](05-plugin-system.md) - Profiles mode in plugins
- [03-users-guide.md](03-users-guide.md) - Using profiles
