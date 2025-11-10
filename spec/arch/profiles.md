# API & MCP Integration Design

## Overview

JN integrates with REST APIs and MCP servers through **profile-based plugins**. The design uses:

- **Two core plugins**: `http` (REST APIs) and `mcp` (MCP servers)
- **Profile-driven config**: Plugins own and validate their profiles
- **Auto-discovery**: No special commands - `jn cat` and `jn put` work with everything
- **Cascading homes**: Multiple JN_HOME locations with priority order

---

## JN_HOME Directory Structure

### Priority Order (Highest to Lowest)

1. **`--home <path>`** - CLI flag (explicit override)
2. **`$JN_HOME`** - Environment variable
3. **`./.jn`** - Current working directory (project-specific)
4. **`~/.local/jn`** - User home (default, avoids polluting ~/)

**Why ~/.local/jn?**
- Follows XDG Base Directory spec
- Doesn't pollute user home with dotfiles
- Standard location for user-specific data

### Discovery Across Homes

Plugins and profiles are discovered across **all** homes in priority order:

```
--home path/         # Highest priority
$JN_HOME/
  ├─ plugins/
  ├─ profiles/

./.jn/               # Project-specific
  ├─ plugins/
  ├─ profiles/

~/.local/jn/         # User defaults (lowest priority)
  ├─ plugins/
  ├─ profiles/
```

**Cascading logic:**
- Plugins: First found wins (allows project overrides)
- Profiles: First found wins (project can override user defaults)
- All homes are checked in order

**Example:**
```bash
# Project profile overrides user profile
./.jn/profiles/http/github.json       # Used (project-specific)
~/.local/jn/profiles/http/github.json # Ignored

# User profile used if no project profile
~/.local/jn/profiles/http/stripe.json # Used (no project override)
```

---

## Profile Structure

### Simple Profile (Single File)

```
~/.local/jn/profiles/
  ├─ http/
  │  ├─ github.json      # All-in-one config
  │  └─ stripe.json
  └─ mcp/
     ├─ context7.json
     └─ filesystem.json
```

**Example (`profiles/http/github.json`):**
```json
{
  "base_url": "https://api.github.com",
  "headers": {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": "Bearer ${GITHUB_TOKEN}"
  },
  "timeout": 30
}
```

### Nested Profile (Directory with Overrides)

```
~/.local/jn/profiles/
  ├─ http/
  │  └─ stripe/
  │     ├─ config.json       # Base config
  │     ├─ charges.json      # Override for /charges
  │     └─ customers.json    # Override for /customers
  └─ mcp/
     └─ context7/
        ├─ config.json       # Base config
        ├─ search.json       # Override for search tool
        └─ ingest.json       # Override for ingest tool
```

**Example (`profiles/http/stripe/config.json`):**
```json
{
  "base_url": "https://api.stripe.com/v1",
  "headers": {
    "Authorization": "Bearer ${STRIPE_SECRET_KEY}"
  },
  "timeout": 30
}
```

**Example (`profiles/http/stripe/charges.json`):**
```json
{
  "timeout": 60,
  "retry": {
    "max_attempts": 5
  }
}
```

**Merged result for `/charges`:**
```json
{
  "base_url": "https://api.stripe.com/v1",
  "headers": {
    "Authorization": "Bearer ${STRIPE_SECRET_KEY}"
  },
  "timeout": 60,          // Overridden
  "retry": {              // Added
    "max_attempts": 5
  }
}
```

### When to Use Each

**Single file** - Use when:
- Simple API with uniform config
- All endpoints use same settings
- Example: GitHub (one token, same headers)

**Nested directory** - Use when:
- Different timeouts per endpoint/tool
- Different retry logic per operation
- Per-resource customization needed
- Example: Stripe (different settings for charges vs customers)

---

## Profile Auto-Detection

Framework automatically detects profile structure:

```python
def load_profile(plugin_name: str, profile_name: str, resource: str = None) -> dict:
    """Load profile, auto-detect single file vs directory."""

    # Check for single file
    profile_file = find_file(f'profiles/{plugin_name}/{profile_name}.json')
    if profile_file:
        return load_and_expand(profile_file)

    # Check for directory with config.json
    profile_dir = find_dir(f'profiles/{plugin_name}/{profile_name}/')
    if profile_dir:
        config = load_and_expand(profile_dir / 'config.json')

        # If resource specified, merge override
        if resource:
            override_file = profile_dir / f'{resource}.json'
            if override_file.exists():
                override = load_and_expand(override_file)
                config = deep_merge(config, override)

        return config

    raise ProfileNotFoundError(f'{plugin_name}/{profile_name}')
```

---

## CLI Syntax

### Basic Usage

```bash
jn cat @profile/resource     # Source (read)
jn put @profile/resource     # Target (write)
```

### HTTP Examples

```bash
# GitHub issues (simple profile)
jn cat @github/repos/anthropics/claude-code/issues

# GitHub specific issue
jn cat @github/repos/anthropics/claude-code/issues/123

# Stripe charges (nested profile, uses charges.json override)
jn cat @stripe/charges?limit=100

# Create Stripe customer
echo '{"email":"user@example.com"}' | jn put @stripe/customers
```

### MCP Examples

```bash
# Context7 search (colon indicates tool name)
jn cat @context7:search --args '{"query":"python asyncio"}'

# Or with stdin
echo '{"query":"python asyncio"}' | jn cat @context7:search

# Context7 ingest (uses ingest.json override for longer timeout)
echo '{"url":"https://..."}' | jn put @context7:ingest

# GitHub MCP create issue
echo '{"repo":"user/repo","title":"Bug"}' | jn put @github:create_issue
```

### Explicit Plugin Specification

When profiles exist in multiple plugins (http and mcp both have github.json):

```bash
# Explicitly use HTTP plugin
jn cat @http/github/repos/anthropics/claude-code/issues

# Explicitly use MCP plugin
jn cat @mcp/github:get_issues
```

**Without explicit plugin (auto-discovery):**
- Searches `profiles/*/github.json` alphabetically
- Finds both `profiles/http/github.json` and `profiles/mcp/github.json`
- Uses first alphabetically: `http`
- Warns: "Multiple profiles 'github' found (http, mcp). Using 'http'. Specify @mcp/github to use the other."

---

## Syntax Detection

Framework routes based on syntax:

### Path-based (HTTP)

```bash
@profile/path/to/resource
@http/profile/path/to/resource
```

**Detection:** Contains `/` after profile name
**Plugin:** `http` (or explicitly specified)
**Example:** `@github/repos/anthropics/claude-code/issues`

### Tool-based (MCP)

```bash
@profile:tool_name
@mcp/profile:tool_name
```

**Detection:** Contains `:` after profile name
**Plugin:** `mcp` (or explicitly specified)
**Example:** `@github:get_issues`

---

## Plugin Responsibilities

### HTTP Plugin (`plugins/http/http.py`)

**Handles:**
- REST API requests (GET, POST, PUT, PATCH, DELETE)
- Path-based resources (`@profile/path`)
- Profile schema validation
- Auth injection
- Pagination (if needed)

**Profile schema:**
```python
PROFILE_SCHEMA = {
  "base_url": str,        # Required
  "headers": dict,        # Optional
  "auth": dict,           # Optional: {"type": "bearer", "token": "..."}
  "timeout": int,         # Optional: default 30
  "retry": dict,          # Optional: {"max_attempts": 3, "backoff": "exponential"}
}
```

**Methods:**
```python
def validate_profile(profile: dict) -> list[str]:
    """Validate profile schema, return errors."""

def profile_schema() -> dict:
    """Return JSON schema for profiles."""

def create_profile_template() -> dict:
    """Return template for new profile."""
```

### MCP Plugin (`plugins/mcp/mcp.py`)

**Handles:**
- MCP server communication
- Tool-based resources (`@profile:tool`)
- Profile schema validation
- Server lifecycle management

**Profile schema:**
```python
PROFILE_SCHEMA = {
  "server": str,          # Required: command to launch server
  "env": dict,            # Optional: environment variables
  "timeout": int,         # Optional: default 30
}
```

**Methods:**
```python
def validate_profile(profile: dict) -> list[str]:
    """Validate profile schema, return errors."""

def profile_schema() -> dict:
    """Return JSON schema for profiles."""

def create_profile_template() -> dict:
    """Return template for new profile."""
```

---

## Schema System

### Three Types of Schemas

**1. Profile Schema** (What config the plugin needs)
- Defined by plugin
- Used for validation
- Example: HTTP needs `base_url`, MCP needs `server`

**2. Output Schema** (What the source returns)
- Defined per source/tool
- Describes NDJSON records output
- Example: GitHub issues returns `{id, title, state, ...}`

**3. Input Schema** (What the target expects)
- Defined per target/tool
- Describes NDJSON records input
- Example: Create issue expects `{title, body, ...}`

### Schema Storage

**Option A: In profile (user-provided)**
```json
{
  "base_url": "https://api.github.com",
  "headers": {...},
  "schemas": {
    "repos/issues": {
      "output": {"type": "object", "properties": {...}},
      "input": {"type": "object", "properties": {...}}
    }
  }
}
```

**Option B: In plugin (plugin-provided)**
```python
def get_schema(resource: str, direction: str) -> dict:
    """Get schema for resource.

    Args:
        resource: e.g., "repos/issues" or "create_issue"
        direction: "output" or "input"

    Returns:
        JSON schema dict
    """
    return SCHEMAS.get(resource, {}).get(direction, {})
```

**Recommendation: Plugin-provided**
- Schemas are domain knowledge (plugin knows API structure)
- Users shouldn't have to define schemas
- Can be overridden in profile if needed

---

## Duck Typing for Plugin Capabilities

Plugins declare capabilities by implementing functions:

### Profile Management (Optional)

```python
def validate_profile(profile: dict) -> list[str]:
    """Validate profile, return errors. Empty list = valid."""

def profile_schema() -> dict:
    """Return JSON schema for profile validation."""

def create_profile_template() -> dict:
    """Return template for 'jn profile create'."""
```

**If not implemented:** Profile validation skipped, no template available.

### Schema Support (Optional)

```python
def get_schema(resource: str, direction: str) -> dict:
    """Return schema for resource.

    Args:
        resource: Resource path/tool name
        direction: "output" (source) or "input" (target)
    """
```

**If not implemented:** No schema validation for data.

### Discovery

```python
from jn.plugins import get_plugin_capabilities

caps = get_plugin_capabilities('http')
# Returns: {"validate_profile": True, "profile_schema": True, "get_schema": True}

if caps['validate_profile']:
    errors = plugin.validate_profile(profile)
```

---

## Real-World Examples

### Example 1: GitHub Issues via HTTP

**Profile (`~/.local/jn/profiles/http/github.json`):**
```json
{
  "base_url": "https://api.github.com",
  "headers": {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": "Bearer ${GITHUB_TOKEN}"
  }
}
```

**Read issues:**
```bash
jn cat @github/repos/anthropics/claude-code/issues
```

**Create issue:**
```bash
echo '{"title":"Bug in X","body":"Description..."}' | \
  jn put @github/repos/myuser/myrepo/issues
```

**How it works:**
1. `@github` → finds `profiles/http/github.json`
2. `/repos/.../issues` → appends to base_url
3. HTTP plugin makes request with headers
4. Returns NDJSON (one issue per line)

### Example 2: GitHub Issues via MCP

**Profile (`~/.local/jn/profiles/mcp/github.json`):**
```json
{
  "server": "docker run -i --rm ghcr.io/github/github-mcp-server",
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}",
    "GITHUB_TOOLSETS": "issues"
  }
}
```

**Read issues:**
```bash
echo '{"repo":"anthropics/claude-code"}' | jn cat @github:get_issues
```

**Create issue:**
```bash
echo '{"repo":"myuser/myrepo","title":"Bug","body":"..."}' | \
  jn put @github:create_issue
```

**How it works:**
1. `@github:get_issues` → colon indicates MCP tool
2. Finds `profiles/mcp/github.json`
3. MCP plugin launches server with env vars
4. Calls `get_issues` tool with stdin as args
5. Returns NDJSON (one issue per line)

### Example 3: Context7 Search (Nested Profile)

**Profile structure:**
```
~/.local/jn/profiles/mcp/context7/
  ├── config.json        # Base config
  ├── search.json        # Override: timeout=60
  └── ingest.json        # Override: timeout=300
```

**config.json:**
```json
{
  "server": "uvx context7",
  "env": {"CONTEXT7_API_KEY": "${CONTEXT7_KEY}"},
  "timeout": 30
}
```

**search.json:**
```json
{
  "timeout": 60,
  "max_results": 100
}
```

**Usage:**
```bash
# Uses config.json + search.json (merged)
echo '{"query":"python asyncio"}' | jn cat @context7:search

# Uses config.json + ingest.json (merged)
echo '{"url":"https://docs.python.org"}' | jn put @context7:ingest
```

**Merged config for search:**
```json
{
  "server": "uvx context7",
  "env": {"CONTEXT7_API_KEY": "${CONTEXT7_KEY}"},
  "timeout": 60,           // From search.json
  "max_results": 100       // From search.json
}
```

### Example 4: Stripe with Multiple Environments

**Profiles:**
```
~/.local/jn/profiles/http/
  ├── stripe-test.json
  └── stripe-prod.json
```

**stripe-test.json:**
```json
{
  "base_url": "https://api.stripe.com/v1",
  "headers": {
    "Authorization": "Bearer ${STRIPE_TEST_KEY}"
  }
}
```

**stripe-prod.json:**
```json
{
  "base_url": "https://api.stripe.com/v1",
  "headers": {
    "Authorization": "Bearer ${STRIPE_PROD_KEY}"
  }
}
```

**Usage:**
```bash
# Test environment
jn cat @stripe-test/charges?limit=10

# Production environment
jn cat @stripe-prod/charges?limit=10
```

---

## Profile Management Commands

### List Profiles

```bash
jn profile list

# Output:
Profiles by plugin:

http:
  - github (~/.local/jn/profiles/http/github.json)
  - stripe-test (~/.local/jn/profiles/http/stripe-test.json)
  - stripe-prod (~/.local/jn/profiles/http/stripe-prod.json)

mcp:
  - github (~/.local/jn/profiles/mcp/github.json)
  - context7 (~/.local/jn/profiles/mcp/context7/)
  - filesystem (~/.local/jn/profiles/mcp/filesystem.json)
```

### Show Profile

```bash
jn profile show http/github

# Output:
Profile: http/github
Location: ~/.local/jn/profiles/http/github.json
Type: single file

Configuration:
{
  "base_url": "https://api.github.com",
  "headers": {
    "Authorization": "Bearer ${GITHUB_TOKEN}"
  }
}

Environment variables:
  ✓ GITHUB_TOKEN (set)
```

### Create Profile

```bash
jn profile create http/myapi

# Creates ~/.local/jn/profiles/http/myapi.json with template:
{
  "base_url": "https://api.example.com",
  "headers": {},
  "timeout": 30
}

# Edit: $EDITOR ~/.local/jn/profiles/http/myapi.json
```

### Validate Profile

```bash
jn profile validate http/github

# Output:
✓ Profile 'http/github' is valid
✓ Schema validation passed
✓ Environment variables defined
  ✓ GITHUB_TOKEN (set)
```

---

## Success Criteria

### For Sources (cat)

**HTTP Source:**
```bash
jn cat @github/repos/anthropics/claude-code/issues
```

**Success:**
- ✅ Profile loaded from correct JN_HOME
- ✅ Environment variables expanded (${GITHUB_TOKEN})
- ✅ Request made to correct URL
- ✅ Headers included (auth, accept)
- ✅ Response parsed as NDJSON
- ✅ Pagination handled automatically (if implemented)
- ✅ Each record output as one JSON line

**MCP Source:**
```bash
echo '{"repo":"anthropics/claude-code"}' | jn cat @github:get_issues
```

**Success:**
- ✅ Profile loaded from correct JN_HOME
- ✅ MCP server launched with env vars
- ✅ Tool called with stdin as args
- ✅ Response streamed as NDJSON
- ✅ Server shutdown cleanly after

### For Targets (put)

**HTTP Target:**
```bash
echo '{"title":"Bug","body":"..."}' | jn put @github/repos/myuser/myrepo/issues
```

**Success:**
- ✅ Profile loaded
- ✅ NDJSON read from stdin
- ✅ POST request made with body
- ✅ Auth headers included
- ✅ Response validated
- ✅ Success/error reported

**MCP Target:**
```bash
echo '{"repo":"myuser/myrepo","title":"Bug"}' | jn put @github:create_issue
```

**Success:**
- ✅ Profile loaded
- ✅ MCP server launched
- ✅ Tool called with stdin as args
- ✅ Response received
- ✅ Server shutdown cleanly

### For Nested Profiles

**Stripe charges with override:**
```bash
jn cat @stripe/charges?limit=10
```

**Success:**
- ✅ Loaded `stripe/config.json`
- ✅ Loaded `stripe/charges.json`
- ✅ Merged configs (charges overrides config)
- ✅ Used merged timeout (60 from charges.json)
- ✅ Made request with base_url from config.json

---

## Environment Variable Expansion

Profiles support environment variable references:

```json
{
  "base_url": "https://api.github.com",
  "headers": {
    "Authorization": "Bearer ${GITHUB_TOKEN}"
  }
}
```

**Expansion rules:**
- `${VAR}` → `os.environ['VAR']` (error if not set)
- `${VAR:-default}` → `os.environ.get('VAR', 'default')`
- Expanded at profile load time
- Applied recursively to all string values

---

## Disambiguation Strategy

When multiple profiles share a name:

```
profiles/http/github.json
profiles/mcp/github.json
```

**Automatic (alphabetical priority):**
```bash
jn cat @github/repos/...
# Finds both, uses 'http' (alphabetically first)
# Warns: "Multiple profiles 'github' found (http, mcp). Using 'http'."
```

**Explicit (no ambiguity):**
```bash
jn cat @http/github/repos/...    # Force http
jn cat @mcp/github:get_issues    # Force mcp
```

---

## Design Principles

### 1. Plugin-Owned Profiles
- Plugins define profile schemas
- Plugins validate profiles
- Framework just loads and routes

### 2. Auto-Discovery
- No special commands for APIs or MCP
- `jn cat` and `jn put` work uniformly
- Syntax hints routing (`:` vs `/`)

### 3. Cascading Configuration
- Multiple JN_HOME locations
- Priority order: CLI > env > local > user
- Project can override user defaults

### 4. Duck Typing
- Plugins implement capabilities optionally
- Framework detects via introspection
- No rigid interface requirements

### 5. Simple by Default
- Single-file profiles for simple cases
- Nested profiles only when needed
- Reasonable defaults everywhere

### 6. Unix Philosophy
- Profiles are just JSON files
- Edit with any text editor
- Version control friendly
- Scriptable and transparent

---

## Migration Path

### From Current State

**Current:**
```bash
jn cat https://api.github.com/repos/anthropics/claude-code/issues
```

**New:**
```bash
# Create profile once
jn profile create http/github
# Edit: add base_url, token

# Use forever
jn cat @github/repos/anthropics/claude-code/issues
```

**Benefits:**
- No hardcoded URLs
- Credentials in profiles (gitignored)
- Reusable across commands
- Team can share project profiles

---

## Future Extensions

**Not in initial design, but compatible:**

- Profile inheritance (`"extends": "base-api"`)
- OpenAPI spec generation (`jn profile generate openapi spec.yaml`)
- Profile encryption (encrypted tokens)
- Remote profiles (fetch from URL)
- Profile templates marketplace

**Current design doesn't prevent these - can add later.**

---

## Summary

**Core design:**
- Two plugins: `http` and `mcp`
- Profile-driven configuration
- Auto-discovery via syntax
- Cascading JN_HOME locations
- Nested profiles for complex cases

**Success = Simple for simple cases, powerful when needed.**
