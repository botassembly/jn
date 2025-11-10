# Profile System Design

## Overview

Profiles provide **connection configuration** for external systems. This is a **planned feature** for v4.2.0 to support REST APIs, MCP servers, and databases.

**Current state:** Basic file/URL routing exists. Profile system is design phase.

## Planned Structure

```
~/.local/jn/profiles/
├── http/                 # HTTP API profiles
│   ├── github.json      # Simple profile (single file)
│   └── stripe/          # Complex profile (directory)
│       ├── config.json  # Base connection config
│       └── charges.json # Per-endpoint overrides
│
├── mcp/                  # MCP server profiles
│   └── github/
│       └── config.json
│
└── sql/                  # Database profiles
    └── mydb/
        ├── config.json  # Database connection
        └── queries/     # Named SQL queries
            └── active-users.sql
```

**Pattern:** Each plugin owns its profile namespace: `profiles/{plugin_name}/`

## Design Goals

### 1. Profiles Are Optional

Direct URLs should work without profiles:

```bash
# Works today (no profile needed)
jn cat https://api.github.com/repos/anthropics/claude-code/issues

# Planned (with profile for convenience)
jn cat @github/repos/anthropics/claude-code/issues
```

Profiles add:
- Authentication
- Custom headers
- Timeouts/retry logic
- Per-endpoint configuration

### 2. Simple by Default, Powerful When Needed

**Simple profile (single file):**
```json
// profiles/http/github.json
{
  "base_url": "https://api.github.com",
  "headers": {
    "Authorization": "Bearer ${GITHUB_TOKEN}"
  }
}
```

**Complex profile (directory with overrides):**
```
profiles/http/stripe/
├── config.json       # Base config
├── charges.json      # Override for /charges
└── customers.json    # Override for /customers
```

### 3. Plugin-Owned Namespaces

Each plugin defines its profile structure:
- `profiles/http/` - HTTP plugin profiles
- `profiles/mcp/` - MCP plugin profiles
- `profiles/sql/` - SQL plugin profiles
- `profiles/jq/` - jq filter definitions

### 4. JN_HOME Cascading

Profiles discovered across JN_HOME locations:

1. `--home <path>` (CLI flag - highest priority)
2. `$JN_HOME` (environment variable)
3. `./.jn` (project-specific)
4. `~/.local/jn` (user home - default)

**First found wins** - allows projects to override user defaults.

## Planned Syntax

**Path-based (/)** - Hierarchical resources:
```bash
@profile/path/to/resource
```

Examples:
- `@github/repos/anthropics/claude-code/issues` (HTTP)
- `@mydb/public/users` (SQL table)

**Tool-based (:)** - Named resources:
```bash
@profile:tool_name
```

Examples:
- `@github:create_issue` (MCP tool)
- `@mydb:active-users` (SQL query)

## Example Profile Structures

### HTTP Profile

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

### MCP Profile

```json
{
  "server": "docker run -i --rm ghcr.io/github/github-mcp-server",
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
  }
}
```

### SQL Profile

```json
{
  "type": "postgresql",
  "host": "localhost",
  "port": 5432,
  "database": "production",
  "user": "admin",
  "password": "${DB_PASSWORD}"
}
```

### jq Profile (Named Filter)

```jq
# profiles/jq/revenue.jq
select(.revenue > 1000) | {id, name, revenue}
```

## Environment Variables

All profiles support environment variable expansion:

```json
{
  "token": "${GITHUB_TOKEN}",     // Error if not set
  "timeout": "${TIMEOUT:-30}"     // Default to 30 if not set
}
```

## Implementation Plan

**Phase 1: Profile Infrastructure**
- Profile discovery across JN_HOME locations
- Environment variable expansion
- Simple profile loading

**Phase 2: HTTP Plugin**
- Generic HTTP plugin with profile support
- Auth helpers (bearer, API key)
- Simple GET/POST support

**Phase 3: MCP Plugin**
- MCP server integration
- Profile-based server launching
- Tool execution

**Phase 4: SQL Plugin**
- Database connections
- Named queries
- Table read/write

## Key Principles

- **Optional** - Direct URIs work without profiles
- **Plugin-owned** - profiles/{plugin_name}/
- **Cascading** - Project can override user defaults
- **Environment-aware** - ${VAR} expansion
- **Simple by default** - Single file for simple cases
- **Powerful when needed** - Directory for overrides

See also:
- `arch/plugins.md` - Plugin system
- `arch/pipeline.md` - Pipeline execution
