# Plugin System

## Overview

JN plugins are **standalone Python scripts** that follow stdin → process → stdout pattern. They're discovered via regex (no imports), declare URI patterns for auto-routing, and can optionally use profiles for configuration.

## Plugin Structure

```
plugins/
├── readers/              # Format parsers (csv, json, xlsx, etc.)
├── writers/              # Format generators (csv, json, xlsx, etc.)
├── filters/              # Transformations (jq, etc.)
├── integrations/         # External system integrations
│   ├── http.py          # HTTP (simple GET + REST API client)
│   ├── s3.py            # S3 storage
│   ├── ftp.py           # FTP
│   ├── mcp.py           # MCP servers
│   └── sql.py           # Databases
└── shell/                # Shell commands (ls, ps, find, etc.)
```

**Key change:** `integrations/` contains ALL external system plugins (previously split between `transports/` and `integrations/`). Whether it's a simple transport (S3) or rich API client (HTTP/SQL/MCP), they all connect to external systems.

## Plugin Discovery

**Locations searched (priority order):**
1. `~/.local/jn/plugins/` (or custom JN_HOME)
2. `./.jn/plugins/` (project-specific)
3. `<package>/plugins/` (built-in)

**Discovery method:** Regex parsing of file contents
- No Python imports needed
- Fast (~10ms for 20+ plugins)
- Extracts META headers, URI patterns, PEP 723 deps

## Plugin META Headers

```python
#!/usr/bin/env python3
# /// script
# dependencies = ["library>=1.0.0"]  # PEP 723
# ///
# META: type=source, handles=[".csv"]
# URI_PATTERNS: ["https://", "http://"]
# KEYWORDS: http, api, rest
# DESCRIPTION: HTTP client for REST APIs

def run(config):
    """Main entry point. Yields NDJSON records."""
    ...
```

**New: URI_PATTERNS** - Declares which URIs this plugin handles.

## URI Pattern Matching

Plugins declare URI patterns they handle. When multiple plugins match, the **most specific** (longest match) wins.

### Examples

**Simple HTTP GET (no profile needed):**
```bash
jn cat https://api.github.com/repos/anthropics/claude-code/issues
```

**Matching logic:**
- `http.py` declares: `URI_PATTERNS: ["https://", "http://"]`
- URL starts with `https://` → http.py handles it
- Makes GET request, returns NDJSON

**Custom company API plugin:**
```python
# ~/.local/jn/plugins/integrations/mycompany_api.py
# META: type=source
# URI_PATTERNS: ["http://api.mycompany.com", "https://api.mycompany.com"]

def run(config):
    # Custom logic for company API
    # - Special auth
    # - Custom error handling
    # - Company-specific transformations
    ...
```

```bash
jn cat http://api.mycompany.com/users
```

**Matching logic:**
- `http.py`: matches `http://` (length 7)
- `mycompany_api.py`: matches `http://api.mycompany.com` (length 24)
- **Winner:** `mycompany_api.py` (most specific)

### Specificity Rules

**Rule:** Longest matching prefix wins

```python
def find_plugin_for_uri(uri: str) -> str:
    """Find best matching plugin for URI."""
    matches = []

    for plugin in discover_plugins():
        for pattern in plugin.uri_patterns:
            if uri.startswith(pattern):
                matches.append((len(pattern), plugin.name))

    if not matches:
        raise NoPluginFoundError(f"No plugin for URI: {uri}")

    # Sort by length (descending), return most specific
    matches.sort(reverse=True, key=lambda x: x[0])
    return matches[1]
```

**Examples:**

| URI | Matches | Winner |
|-----|---------|--------|
| `http://example.com/data` | `http.py` ("http://", len=7) | http.py |
| `s3://bucket/file` | `s3.py` ("s3://", len=5) | s3.py |
| `http://api.mycompany.com/users` | `http.py` (7), `mycompany_api.py` (24) | mycompany_api.py |
| `https://api.stripe.com/charges` | `http.py` (8), `stripe_plugin.py` (25) | stripe_plugin.py |

## Profiles vs Direct URIs

**Profiles are optional convenience** - plugins work without them.

### Without Profile (Direct URI)

```bash
jn cat https://api.github.com/repos/anthropics/claude-code/issues
```

Plugin receives minimal config:
```python
config = {
    'url': 'https://api.github.com/repos/anthropics/claude-code/issues'
}
```

Makes simple GET request.

### With Profile (Enhanced Config)

```bash
jn cat @github/repos/anthropics/claude-code/issues
```

Plugin receives rich config:
```python
config = {
    'url': 'https://api.github.com/repos/anthropics/claude-code/issues',
    'base_url': 'https://api.github.com',
    'headers': {
        'Authorization': 'Bearer ghp_...',
        'Accept': 'application/vnd.github.v3+json'
    },
    'timeout': 30,
    'retry': {'max_attempts': 3}
}
```

## Profile Organization

Profiles are **named after plugins** and stored in `profiles/{plugin_name}/`.

```
~/.local/jn/profiles/
├── jq/                   # jq filter definitions
│   ├── revenue.jq
│   └── clean-nulls.jq
│
├── http/                 # HTTP API profiles
│   ├── github.json
│   └── stripe/
│       ├── config.json
│       └── charges.json
│
├── mcp/                  # MCP server profiles
│   └── github/
│       └── config.json
│
└── sql/                  # Database profiles
    └── mydb/
        ├── config.json
        └── queries/
            └── active-users.sql
```

**Pattern:** Each plugin owns its profile namespace.

## Plugin Types

**Sources** - Read data → output NDJSON
- Readers: Parse formats (csv_reader, xlsx_reader)
- Integrations: Fetch from external systems (http, s3, sql)
- Shell: Execute commands (ls, ps, find)

**Filters** - Transform NDJSON → NDJSON
- jq: JSON filtering/transformation

**Targets** - Read NDJSON → write output
- Writers: Generate formats (csv_writer, json_writer)
- Integrations: Send to external systems (http, sql)

## Integration Plugin Examples

### HTTP Plugin

```python
# plugins/integrations/http.py
# META: type=source, target
# URI_PATTERNS: ["https://", "http://"]

def run(config):
    """HTTP client - works with or without profile."""
    url = config['url']
    headers = config.get('headers', {})

    # Make request
    result = subprocess.run(['curl', '-H', ..., url], ...)

    # Parse JSON response
    data = json.loads(result.stdout)

    # Handle arrays or objects
    if isinstance(data, list):
        for item in data:
            yield item
    else:
        yield data
```

**Works both ways:**
```bash
# Direct (no profile)
jn cat https://httpbin.org/json

# With profile (adds auth, etc.)
jn cat @github/repos/anthropics/claude-code/issues
```

### S3 Plugin

```python
# plugins/integrations/s3.py
# META: type=source, target
# URI_PATTERNS: ["s3://"]

def run(config):
    """S3 client - uses AWS CLI."""
    url = config['url']
    profile = config.get('aws_profile')

    # Build command
    cmd = ['aws', 's3', 'cp', url, '-']
    if profile:
        cmd.extend(['--profile', profile])

    # Stream bytes
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    ...
```

**Works both ways:**
```bash
# Direct (uses default AWS credentials)
jn cat s3://bucket/file.csv

# With profile (specific AWS account)
jn cat @work-s3/bucket/file.csv
```

### jq Plugin with Named Filters

```python
# plugins/filters/jq.py
# META: type=filter

def run(config):
    """jq filter - supports inline or named."""
    expression = config['expression']

    # If starts with @, load from profiles/jq/
    if expression.startswith('@'):
        name = expression[1:]
        filter_path = find_profile_file('jq', f'{name}.jq')
        expression = filter_path.read_text()

    # Execute jq
    jq_process = subprocess.Popen(
        ['jq', '-c', expression],
        stdin=sys.stdin,
        stdout=subprocess.PIPE
    )

    for line in jq_process.stdout:
        yield json.loads(line)
```

**Named filters:**
```jq
# ~/.local/jn/profiles/jq/revenue.jq
select(.revenue > 1000) | {id, name, revenue}
```

**Usage:**
```bash
# Inline
jn cat data.csv | jn filter jq '.revenue > 1000'

# Named (auto-discovers profiles/jq/revenue.jq)
jn cat data.csv | jn filter jq @revenue
```

### SQL Plugin

```python
# plugins/integrations/sql.py
# META: type=source, target
# URI_PATTERNS: []  # Only via @profile syntax

def run(config):
    """SQL client - requires profile."""
    profile_name = config['profile']
    resource = config['resource']

    # Load connection
    profile = load_profile('sql', profile_name)
    conn = connect(profile)

    # Check if table path or named query
    if ':' in resource:
        # Named query: @mydb:active-users
        query_name = resource.split(':')[1]
        sql = load_query(profile_name, query_name)
    else:
        # Table path: @mydb/public/users
        schema, table = parse_table_path(resource)
        sql = f"SELECT * FROM {schema}.{table}"

    # Execute and yield NDJSON
    for row in execute(conn, sql):
        yield dict(row)
```

**Profile structure:**
```
profiles/sql/mydb/
├── config.json          # Connection: host, port, user, pass, db
└── queries/
    └── active-users.sql # SELECT * FROM users WHERE active = true
```

**Usage:**
```bash
# Table
jn cat @mydb/public/users

# Named query
jn cat @mydb:active-users
```

## Custom Plugin Development

**Create company-specific plugin:**

```python
# ~/.local/jn/plugins/integrations/mycompany_api.py
#!/usr/bin/env python3
# META: type=source
# URI_PATTERNS: ["http://api.mycompany.com", "https://api.mycompany.com"]
# DESCRIPTION: MyCompany API client with custom auth

import sys
import json
import subprocess

def run(config):
    """Custom API client."""
    url = config['url']

    # Company-specific auth
    api_key = os.environ['MYCOMPANY_API_KEY']

    # Make request with custom headers
    result = subprocess.run([
        'curl', '-H', f'X-API-Key: {api_key}',
        '-H', 'X-Client: jn-etl',
        url
    ], capture_output=True, text=True)

    # Custom response handling
    data = json.loads(result.stdout)

    # Transform to NDJSON
    for item in data['results']:
        yield {
            'id': item['id'],
            'name': item['name'],
            # Company-specific transformations
        }
```

**Automatically used:**
```bash
# Uses mycompany_api.py (most specific match)
jn cat http://api.mycompany.com/users

# Generic http.py would only be used for other domains
jn cat http://other-api.com/data
```

## Registry Updates

The registry now supports URI pattern matching:

```python
class Registry:
    def get_plugin_for_source(self, source: str) -> str:
        """Find plugin for source (file, URL, or @profile)."""

        # Check for @profile syntax
        if source.startswith('@'):
            return self.get_plugin_for_profile(source)

        # Check for URI pattern match
        if '://' in source:
            return self.get_plugin_for_uri(source)

        # Check for file extension
        ext = Path(source).suffix
        return self.get_plugin_for_extension(ext)
```

## Key Principles

- **Specificity wins** - Longest URI match takes precedence
- **Profiles optional** - Direct URIs work without profiles
- **Plugin-owned profiles** - profiles/{plugin_name}/
- **Custom plugins override** - User plugins can override built-ins
- **Zero coupling** - Plugins don't know about each other

See also:
- `arch/backpressure.md` - Streaming details
- `arch/pipeline.md` - Pipeline execution
- `arch/profiles.md` - Profile system design
