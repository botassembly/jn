# REST API Profile System - Design Document

## Overview

Profile system for REST APIs that provides reusable connection configurations, path resolution, and authentication. Enables clean `@profile/path` syntax for accessing API endpoints.

## Core Concept

Profiles define:
1. **Base URL** - API root endpoint
2. **Authentication** - Headers, API keys, OAuth tokens
3. **Path templates** - URL path resolution with variables
4. **Default parameters** - Query params, headers, pagination settings

## Profile Structure

### Basic Profile
`~/.local/jn/profiles/http/github.json`
```json
{
  "base_url": "https://api.github.com",
  "headers": {
    "Accept": "application/vnd.github+json",
    "Authorization": "Bearer ${GITHUB_TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28"
  },
  "timeout": 30,
  "rate_limit": {
    "requests_per_second": 10
  }
}
```

### Advanced Profile with Path Templates
`~/.local/jn/profiles/http/restful-api.json`
```json
{
  "base_url": "https://api.restful-api.dev",
  "description": "RESTful API Dev - Sample REST API for testing",
  "headers": {
    "Content-Type": "application/json"
  },
  "paths": {
    "objects": "/objects",
    "object_by_id": "/objects/{id}",
    "search": "/objects?name={query}"
  },
  "methods": {
    "list_objects": {
      "path": "/objects",
      "method": "GET",
      "description": "List all objects"
    },
    "get_object": {
      "path": "/objects/{id}",
      "method": "GET",
      "description": "Get object by ID"
    },
    "create_object": {
      "path": "/objects",
      "method": "POST",
      "description": "Create new object",
      "example_data": {
        "name": "Apple MacBook Pro 16",
        "data": {
          "year": 2019,
          "price": 1849.99,
          "CPU model": "Intel Core i9",
          "Hard disk size": "1 TB"
        }
      }
    }
  }
}
```

### Profile with OAuth
`~/.local/jn/profiles/http/stripe.json`
```json
{
  "base_url": "https://api.stripe.com/v1",
  "auth": {
    "type": "bearer",
    "token": "${STRIPE_API_KEY}"
  },
  "headers": {
    "Stripe-Version": "2023-10-16"
  },
  "paths": {
    "customers": "/customers",
    "customer_by_id": "/customers/{id}",
    "charges": "/charges",
    "invoices": "/invoices"
  }
}
```

## Profile Syntax

### Path-based References
```bash
# Simple path
@github/users/octocat
# Resolves to: https://api.github.com/users/octocat

# Nested path
@github/repos/anthropics/claude-code/issues
# Resolves to: https://api.github.com/repos/anthropics/claude-code/issues

# With query parameters
@github/search/repositories?q=language:python
# Resolves to: https://api.github.com/search/repositories?q=language:python
```

### Method-based References
```bash
# Named method from profile
jn cat @restful-api:list_objects

# Named method with parameters
jn cat @restful-api:get_object --id 3

# POST with data
echo '{"name":"Test","data":{"color":"red"}}' | \
  jn cat @restful-api:create_object --method POST
```

### Parameter Substitution
```bash
# Path variables (replace {id} in template)
jn cat @restful-api/objects/3
# Uses path template: /objects/{id}
# Resolves to: https://api.restful-api.dev/objects/3

# Named parameters
jn cat @stripe/customers/{customer_id} --customer_id "cus_123"
# Resolves to: https://api.stripe.com/v1/customers/cus_123
```

## Profile Discovery

### Search Paths (priority order)
1. Project-local: `.jn/profiles/http/`
2. User profiles: `~/.local/jn/profiles/http/`
3. Bundled profiles: `jn_home/profiles/http/`

### Profile Resolution Algorithm
```python
def resolve_profile_reference(ref: str) -> dict:
    """Resolve @profile/path to full URL with config.

    Examples:
        @github/users/octocat
        @restful-api:list_objects
        @stripe/customers/{id} --id cus_123
    """
    # Parse reference
    if ':' in ref:
        # Method-based: @profile:method_name
        profile_name, method_name = ref.split(':', 1)
        profile = load_profile(profile_name)
        method_config = profile['methods'][method_name]
        url = profile['base_url'] + method_config['path']
        method = method_config.get('method', 'GET')
    else:
        # Path-based: @profile/path/to/resource
        parts = ref.split('/', 1)
        profile_name = parts[0]
        path = '/' + parts[1] if len(parts) > 1 else ''

        profile = load_profile(profile_name)
        url = profile['base_url'] + path
        method = 'GET'

    # Build config
    config = {
        'url': url,
        'method': method,
        'headers': profile.get('headers', {}),
        'timeout': profile.get('timeout', 30),
        'verify_ssl': profile.get('verify_ssl', True)
    }

    # Substitute environment variables in headers
    for key, value in config['headers'].items():
        if isinstance(value, str) and '${' in value:
            config['headers'][key] = substitute_env_vars(value)

    return config

def substitute_env_vars(value: str) -> str:
    """Substitute ${VAR} with environment variable value."""
    import os
    import re

    def replace(match):
        var_name = match.group(1)
        return os.environ.get(var_name, '')

    return re.sub(r'\$\{(\w+)\}', replace, value)
```

## CLI Integration

### Enhanced `jn cat` Command
```bash
# Detect profile reference and resolve
if source.startswith('@'):
    profile_config = resolve_profile_reference(source)
    # Pass config to HTTP plugin
    return http_plugin.reads(profile_config)
```

### Profile Management Commands
```bash
# List all profiles
jn profile list

# Show profile details
jn profile info github

# Test profile connection
jn profile test github

# Create new profile from template
jn profile create myapi --base-url https://api.example.com

# Validate profile
jn profile validate github
```

## Usage Examples

### Example 1: GitHub API
**Profile:** `~/.local/jn/profiles/http/github.json`
```json
{
  "base_url": "https://api.github.com",
  "headers": {
    "Authorization": "Bearer ${GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
  }
}
```

**Usage:**
```bash
# List repos for a user
jn cat @github/users/octocat/repos | jn filter '.name'

# Get repo issues
jn cat @github/repos/anthropics/claude-code/issues | jn jtbl

# Search repositories
jn cat '@github/search/repositories?q=language:python&sort=stars' | \
  jn filter '.items[] | {name: .name, stars: .stargazers_count}'
```

### Example 2: RESTful API Dev
**Profile:** `~/.local/jn/profiles/http/restful-api.json`
```json
{
  "base_url": "https://api.restful-api.dev",
  "paths": {
    "objects": "/objects",
    "object": "/objects/{id}"
  }
}
```

**Usage:**
```bash
# List all objects
jn cat @restful-api/objects

# Get specific object
jn cat @restful-api/objects/3

# Filter and transform
jn cat @restful-api/objects | \
  jn filter '.[] | select(.data != null) | {name: .name, price: .data.price}'

# Create new object (POST)
echo '{"name":"Test Device","data":{"color":"blue"}}' | \
  jn http @restful-api/objects --method POST | jn put result.json
```

### Example 3: Multiple APIs in Pipeline
```bash
# Fetch from one API, transform, post to another
jn cat @source-api/data | \
  jn filter '@analytics/transform' | \
  jn http @destination-api/import --method POST
```

### Example 4: OpenCode Config
```bash
# Fetch OpenCode config
jn cat https://opencode.ai/config.json

# Or with profile
# Profile: restful-api-dev.json with base_url: https://opencode.ai
jn cat @opencode/config.json

# Process config
jn cat https://opencode.ai/config.json | \
  jn filter '.features | to_entries | .[] | {feature: .key, enabled: .value}' | \
  jn put features.csv
```

## Implementation

### Profile Loader
```python
# src/jn/profiles/http.py
from pathlib import Path
import json
import os
from typing import Optional, Dict

def load_profile(profile_name: str) -> Dict:
    """Load HTTP profile from search paths."""
    search_paths = [
        Path.cwd() / ".jn" / "profiles" / "http" / f"{profile_name}.json",
        Path.home() / ".local" / "jn" / "profiles" / "http" / f"{profile_name}.json",
        Path(__file__).parent.parent.parent / "jn_home" / "profiles" / "http" / f"{profile_name}.json"
    ]

    for path in search_paths:
        if path.exists():
            with open(path) as f:
                return json.load(f)

    raise FileNotFoundError(f"Profile '{profile_name}' not found in: {[str(p) for p in search_paths]}")

def resolve_url(profile_ref: str, params: Optional[Dict] = None) -> tuple[str, Dict]:
    """Resolve profile reference to URL and config.

    Returns:
        (url, config) tuple
    """
    params = params or {}

    # Strip @ prefix
    ref = profile_ref.lstrip('@')

    # Parse profile reference
    if ':' in ref:
        # Method-based reference
        profile_name, method_name = ref.split(':', 1)
        profile = load_profile(profile_name)
        method = profile['methods'][method_name]
        path = method['path']
        http_method = method.get('method', 'GET')
    else:
        # Path-based reference
        parts = ref.split('/', 1)
        profile_name = parts[0]
        path = '/' + parts[1] if len(parts) > 1 else '/'
        profile = load_profile(profile_name)
        http_method = 'GET'

    # Substitute path variables
    for key, value in params.items():
        path = path.replace(f'{{{key}}}', str(value))

    # Build URL
    base_url = profile['base_url'].rstrip('/')
    url = base_url + path

    # Build config
    config = {
        'url': url,
        'method': http_method,
        'headers': substitute_env_vars(profile.get('headers', {})),
        'timeout': profile.get('timeout', 30),
    }

    if 'auth' in profile:
        config['auth'] = profile['auth']

    return url, config

def substitute_env_vars(headers: Dict) -> Dict:
    """Replace ${VAR} with environment variables."""
    import re

    result = {}
    for key, value in headers.items():
        if isinstance(value, str):
            # Replace ${VAR_NAME}
            def replace(match):
                var = match.group(1)
                return os.environ.get(var, match.group(0))
            result[key] = re.sub(r'\$\{(\w+)\}', replace, value)
        else:
            result[key] = value

    return result
```

### Enhanced HTTP Plugin Integration
```python
# In http_.py reads() function
def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Fetch HTTP endpoint - supports profiles."""
    config = config or {}

    # Get URL from config or stdin
    url = config.get('url')
    if not url:
        url = sys.stdin.read().strip()

    # Check if it's a profile reference
    if url.startswith('@'):
        from jn.profiles.http import resolve_url
        url, profile_config = resolve_url(url, config.get('params', {}))
        # Merge profile config with provided config
        config = {**profile_config, **config}
        config['url'] = url

    # Continue with HTTP request...
```

## Bundled Profiles

Include common API profiles out-of-the-box:

### `jn_home/profiles/http/restful-api.json`
```json
{
  "base_url": "https://api.restful-api.dev",
  "description": "RESTful API Dev - Demo API for testing",
  "paths": {
    "objects": "/objects",
    "object": "/objects/{id}"
  }
}
```

### `jn_home/profiles/http/httpbin.json`
```json
{
  "base_url": "https://httpbin.org",
  "description": "HTTPBin - HTTP testing service",
  "paths": {
    "get": "/get",
    "post": "/post",
    "headers": "/headers",
    "ip": "/ip",
    "user_agent": "/user-agent"
  }
}
```

### `jn_home/profiles/http/jsonplaceholder.json`
```json
{
  "base_url": "https://jsonplaceholder.typicode.com",
  "description": "JSONPlaceholder - Fake REST API",
  "paths": {
    "posts": "/posts",
    "post": "/posts/{id}",
    "users": "/users",
    "user": "/users/{id}",
    "comments": "/comments"
  }
}
```

## Testing Strategy

```python
def test_profile_resolution():
    """Test profile reference resolution."""
    # Create test profile
    profile = {
        "base_url": "https://api.example.com",
        "headers": {"Authorization": "Bearer test123"}
    }

    url, config = resolve_url("@example/users/123", profile)
    assert url == "https://api.example.com/users/123"
    assert config['headers']['Authorization'] == "Bearer test123"

def test_path_variable_substitution():
    """Test path variable substitution."""
    profile = {
        "base_url": "https://api.example.com",
        "paths": {
            "user": "/users/{id}"
        }
    }

    url, config = resolve_url("@example:user", profile, {"id": "456"})
    assert url == "https://api.example.com/users/456"

def test_env_var_substitution():
    """Test environment variable substitution in headers."""
    os.environ['TEST_TOKEN'] = 'secret123'

    headers = substitute_env_vars({
        "Authorization": "Bearer ${TEST_TOKEN}",
        "X-Custom": "value"
    })

    assert headers['Authorization'] == "Bearer secret123"
    assert headers['X-Custom'] == "value"
```

## Security Considerations

1. **Environment Variables**: Always use `${VAR}` for secrets, never hardcode
2. **SSL Verification**: Default to `verify_ssl: true`
3. **Token Exposure**: Tokens never logged or printed to stdout
4. **Profile Permissions**: Warn if profile files have insecure permissions (world-readable)

## Future Enhancements

1. **API Key Rotation**: Automatic token refresh
2. **OpenAPI Integration**: Generate profiles from OpenAPI/Swagger specs
3. **Rate Limiting**: Built-in rate limiting and retry logic
4. **Response Caching**: Cache responses for repeated queries
5. **Pagination Helpers**: Auto-paginate through multi-page responses
6. **GraphQL Support**: GraphQL query syntax in profiles
7. **Webhooks**: Listen for webhook events from APIs

## Integration Examples

### Combined with JQ Profiles
```bash
# Fetch data, pivot, output
jn cat @github/repos/microsoft/vscode/stargazers | \
  jn filter '@builtin/group_count' --by location | \
  jn filter '@builtin/stats' --field count
```

### API-to-Database Pipeline
```bash
# Fetch from API, transform, load to database
jn cat @source-api/daily-metrics | \
  jn filter '@analytics/clean' | \
  jn put @postgres/metrics_table
```

### Multi-API Aggregation
```bash
# Fetch from multiple APIs and merge
jn cat @api1/data @api2/data @api3/data | \
  jn filter '@builtin/flatten_nested' | \
  jn put aggregated.csv
```
