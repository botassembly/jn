# Profile System

## Overview

Profiles provide **connection configuration** and **named resources** for plugins that integrate with external systems. Profiles are **named after plugins** and stored in `profiles/{plugin_name}/`.

## Structure

```
~/.local/jn/profiles/
├── jq/                   # jq plugin profiles
│   ├── revenue.jq       # Named filter
│   └── clean-nulls.jq   # Named filter
│
├── http/                 # HTTP plugin profiles
│   ├── github.json      # Simple profile (single file)
│   └── stripe/          # Complex profile (directory)
│       ├── config.json  # Base connection config
│       └── charges.json # Per-endpoint overrides
│
├── mcp/                  # MCP plugin profiles
│   └── github/
│       └── config.json
│
└── sql/                  # SQL plugin profiles
    └── mydb/
        ├── config.json  # Database connection
        └── queries/     # Named SQL queries
            └── active-users.sql
```

**Pattern:** Each plugin owns its profile namespace: `profiles/{plugin_name}/`

## JN_HOME Priority

Profiles discovered across all JN_HOME locations (highest to lowest priority):

1. `--home <path>` (CLI flag)
2. `$JN_HOME` (environment variable)
3. `./.jn` (current working directory - project-specific)
4. `~/.local/jn` (user home - default)

**First found wins** - allows project to override user defaults.

## Profile Types

### Simple Profile (Single File)

For plugins with uniform configuration:

```json
// profiles/http/github.json
{
  "base_url": "https://api.github.com",
  "headers": {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": "Bearer ${GITHUB_TOKEN}"
  },
  "timeout": 30
}
```

**Usage:**
```bash
jn cat @github/repos/anthropics/claude-code/issues
```

### Complex Profile (Directory with Overrides)

For plugins needing per-resource customization:

```
profiles/http/stripe/
├── config.json       # Base connection config
├── charges.json      # Override for /charges endpoint
└── customers.json    # Override for /customers endpoint
```

**Merged config example:** When accessing `/charges`, `config.json` and `charges.json` are deep merged.

**Usage:**
```bash
jn cat @stripe/charges?limit=10
# Uses config.json + charges.json (merged)
```

## Plugin-Specific Examples

### HTTP Profiles

```json
{
  "base_url": "https://api.example.com",
  "headers": {},
  "timeout": 30,
  "retry": {"max_attempts": 3}
}
```

```bash
jn cat @github/repos/anthropics/claude-code/issues
```

### MCP Profiles

```json
{
  "server": "docker run -i --rm ghcr.io/github/github-mcp-server",
  "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"}
}
```

```bash
jn cat @github:get_issues
```

### SQL Profiles

```json
{
  "type": "postgresql",
  "host": "localhost",
  "port": 5432,
  "database": "production"
}
```

```bash
jn cat @mydb/public/users
jn cat @mydb:active-users
```

### jq Profiles (Named Filters)

```jq
# profiles/jq/revenue.jq
select(.revenue > 1000) | {id, name, revenue}
```

```bash
jn cat data.csv | jn filter jq @revenue
```

## Environment Variable Expansion

```json
{
  "token": "${GITHUB_TOKEN}",     // Error if not set
  "timeout": "${TIMEOUT:-30}"     // Default to 30
}
```

## Syntax Patterns

**Path-based (/):** `@profile/path/to/resource`
- `@github/repos/anthropics/claude-code/issues`
- `@mydb/public/users`

**Tool-based (:):** `@profile:tool_name`
- `@github:get_issues`
- `@mydb:active-users`

## Key Principles

- **Plugin-owned** - profiles/{plugin_name}/
- **Optional** - Direct URIs work without profiles
- **Cascading** - Project can override user
- **Simple by default** - Single file for simple cases
- **Powerful when needed** - Directory for overrides

See also: `arch/plugins.md` for plugin system details
