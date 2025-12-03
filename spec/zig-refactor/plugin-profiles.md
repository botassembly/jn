# Plugin-Defined Profiles

> **Proposal**: Make profiles a first-class part of the plugin specification, alongside `read`, `write`, and `raw` modes.

---

## Current State

**Profiles are filesystem-based and separate from plugins:**

```
profiles/
├── http/
│   └── myapi/
│       ├── _meta.json      # Base config
│       └── users.json      # Endpoint definition
├── zq/
│   └── sales/
│       └── by_region.zq    # Filter expression
└── gmail/
    └── inbox.json          # Gmail query defaults
```

**Problems:**
1. Profiles are discovered separately from plugins
2. No dynamic profile discovery (must pre-define all endpoints)
3. Profile format varies by type (JSON vs .zq files)
4. Can't introspect what profiles a plugin supports

---

## Proposed: Profiles as Plugin Capability

### Plugin Metadata Extension

Add `profiles` to the plugin specification:

```json
{
  "name": "http",
  "version": "0.1.0",
  "matches": ["^https?://"],
  "role": "protocol",
  "modes": ["read", "write", "raw", "profiles"],
  "profile_type": "http"
}
```

The `"profiles"` mode indicates the plugin can:
1. List available profiles (`--mode=profiles --list`)
2. Provide profile details (`--mode=profiles --info=@namespace/name`)
3. Discover profiles dynamically (`--mode=profiles --discover=<url>`)

### Plugin Profile Interface

**List profiles:**
```bash
http --mode=profiles --list
```

Output (NDJSON):
```json
{"reference": "@myapi/users", "description": "List users", "params": ["limit", "offset"]}
{"reference": "@myapi/projects", "description": "List projects", "params": ["status"]}
```

**Get profile info:**
```bash
http --mode=profiles --info=@myapi/users
```

Output:
```json
{
  "reference": "@myapi/users",
  "description": "List users from MyAPI",
  "params": ["limit", "offset", "filter"],
  "defaults": {"limit": 100},
  "url_template": "https://api.myservice.com/v1/users",
  "examples": [
    {"usage": "jn cat @myapi/users?limit=10", "description": "Get first 10 users"}
  ]
}
```

**Discover profiles (dynamic):**
```bash
http --mode=profiles --discover=https://api.myservice.com
```

Output: Discovered endpoints as profile definitions

### Profile Storage

Profiles can come from multiple sources:

1. **Bundled with plugin** - Plugin includes default profiles
2. **Filesystem** - User-defined in `~/.local/jn/profiles/`
3. **Dynamic discovery** - Plugin discovers at runtime

Priority: User filesystem > Plugin bundled > Dynamic

### Plugin Implementation Examples

#### Python Plugin with Profiles

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["duckdb"]
# [tool.jn]
# matches = ["^duckdb://", ".*\\.duckdb$"]
# role = "database"
# modes = ["read", "profiles"]
# profile_type = "duckdb"
# ///
"""DuckDB plugin with dynamic profile discovery."""

import json
import duckdb

def reads(config):
    """Execute query and stream results."""
    conn = duckdb.connect(config.get('database', ':memory:'))
    query = config.get('query', 'SELECT 1')
    for row in conn.execute(query).fetchall():
        print(json.dumps(dict(row)), flush=True)

def profiles_list(config):
    """List available tables as profiles."""
    db_path = config.get('database')
    if not db_path:
        return

    conn = duckdb.connect(db_path)
    tables = conn.execute("SHOW TABLES").fetchall()

    for (table_name,) in tables:
        print(json.dumps({
            "reference": f"@duckdb/{table_name}",
            "description": f"Query {table_name} table",
            "params": ["columns", "where", "limit"],
            "defaults": {"columns": "*"}
        }), flush=True)

def profiles_info(config):
    """Get detailed profile info."""
    profile_name = config.get('profile')
    db_path = config.get('database')

    conn = duckdb.connect(db_path)
    # Get table schema
    columns = conn.execute(f"DESCRIBE {profile_name}").fetchall()

    print(json.dumps({
        "reference": f"@duckdb/{profile_name}",
        "description": f"Query {profile_name} table",
        "schema": [{"name": c[0], "type": c[1]} for c in columns],
        "params": ["columns", "where", "limit", "order_by"],
        "examples": [
            {"usage": f"jn cat @duckdb/{profile_name}?limit=10"}
        ]
    }))

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', default='read')
    parser.add_argument('--jn-meta', action='store_true')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--info')
    parser.add_argument('--database')
    parser.add_argument('--query')
    args = parser.parse_args()

    if args.jn_meta:
        print(json.dumps({
            "name": "duckdb",
            "matches": ["^duckdb://", ".*\\.duckdb$"],
            "role": "database",
            "modes": ["read", "profiles"],
            "profile_type": "duckdb"
        }))
    elif args.mode == 'profiles':
        if args.list:
            profiles_list(vars(args))
        elif args.info:
            profiles_info({'profile': args.info, **vars(args)})
    elif args.mode == 'read':
        reads(vars(args))
```

**Usage:**
```bash
# List available profiles (tables)
jn profile list --type=duckdb --database=sales.duckdb

# Query via profile
jn cat "@duckdb/customers?where=region='East'&limit=100"
```

#### Zig Plugin with Bundled Profiles

```zig
// plugins/zig/http/main.zig

const bundled_profiles = [_]Profile{
    .{
        .reference = "@github/repos",
        .description = "List GitHub repositories",
        .url_template = "https://api.github.com/users/{user}/repos",
        .params = &.{"user", "per_page", "sort"},
    },
    .{
        .reference = "@github/issues",
        .description = "List repository issues",
        .url_template = "https://api.github.com/repos/{owner}/{repo}/issues",
        .params = &.{"owner", "repo", "state", "per_page"},
    },
};

fn profiles_list(writer: anytype) !void {
    // First output bundled profiles
    for (bundled_profiles) |profile| {
        try outputProfileJson(writer, profile);
    }

    // Then scan filesystem for user profiles
    try scanFilesystemProfiles(writer);
}

fn profiles_info(writer: anytype, reference: []const u8) !void {
    // Check bundled first
    for (bundled_profiles) |profile| {
        if (std.mem.eql(u8, profile.reference, reference)) {
            try outputProfileDetailJson(writer, profile);
            return;
        }
    }

    // Check filesystem
    try loadFilesystemProfile(writer, reference);
}
```

### Discovery Service Integration

The Zig discovery service queries plugins for profiles:

```zig
// libs/zig/jn-discovery/profiles.zig

pub fn discoverProfiles(allocator: Allocator) ![]ProfileInfo {
    var all_profiles = std.ArrayList(ProfileInfo).init(allocator);

    // 1. Query each plugin that supports 'profiles' mode
    for (plugins) |plugin| {
        if (plugin.supportsMode(.profiles)) {
            const output = try execPlugin(plugin, &.{"--mode=profiles", "--list"});
            try parseProfilesOutput(&all_profiles, output);
        }
    }

    // 2. Also scan filesystem for static profiles
    try scanFilesystemProfiles(&all_profiles);

    // 3. Deduplicate (plugin bundled < filesystem)
    return deduplicateProfiles(all_profiles.items);
}
```

### Profile Resolution Flow

```
User runs: jn cat @myapi/users?limit=10

1. Parse reference: @myapi/users

2. Find profile:
   a. Check filesystem: ~/.local/jn/profiles/http/myapi/users.json
   b. If not found, ask http plugin: http --mode=profiles --info=@myapi/users
   c. Plugin returns profile definition

3. Resolve to URL:
   - Base URL from profile
   - Substitute parameters
   - Add auth headers from profile

4. Execute:
   - jn-cat spawns http plugin with resolved URL + headers
```

---

## Benefits

### 1. Unified Plugin Interface

```
Plugin Modes:
├── read     - Read data → NDJSON
├── write    - NDJSON → Write data
├── raw      - Byte passthrough
└── profiles - List/describe available profiles
```

Every plugin uses the same interface. Discovery is uniform.

### 2. Dynamic Profile Discovery

**DuckDB**: Discover tables in a database
```bash
jn profile list --type=duckdb --database=analytics.duckdb
# Lists all tables as profiles
```

**HTTP**: Discover API endpoints (if API supports it)
```bash
jn profile discover https://api.myservice.com
# Reads OpenAPI spec, creates profiles
```

**MCP**: Discover tools and resources
```bash
jn profile list --type=mcp --server=biomcp
# Lists tools from MCP server
```

### 3. Language Agnostic

Any executable that implements the interface works:

```bash
# Python plugin
python duckdb_.py --mode=profiles --list

# Zig plugin
./http --mode=profiles --list

# Shell script plugin
./custom-api.sh --mode=profiles --list

# Even a simple curl wrapper
./rest-wrapper --mode=profiles --list
```

### 4. Bundled + User Profiles

Plugins can ship with useful defaults:

```
http plugin bundles:
├── @github/repos
├── @github/issues
├── @github/users
├── @jsonplaceholder/posts
└── @jsonplaceholder/users

User can add:
├── @mycompany/users
└── @mycompany/products
```

### 5. Introspection

```bash
# What can this plugin do?
jn plugin info http
# Shows: modes=[read, raw, profiles], bundled profiles, ...

# What profiles are available?
jn profile list
# Aggregates from all plugins + filesystem

# Details about a specific profile
jn profile info @myapi/users
# Shows: URL, params, auth, examples
```

---

## Implementation Changes

### Plugin Metadata

Add to `--jn-meta` output:

```json
{
  "name": "http",
  "modes": ["read", "raw", "profiles"],
  "profile_type": "http",
  "bundled_profiles": ["@github/repos", "@github/issues"]
}
```

### CLI Interface

```bash
# Plugin-level profile listing
plugin --mode=profiles --list [--database=X]

# Plugin-level profile info
plugin --mode=profiles --info=@namespace/name

# Plugin-level profile discovery (optional)
plugin --mode=profiles --discover=<url>
```

### jn profile Command

```bash
# List all profiles (queries all plugins)
jn profile list [--type=X]

# Profile info (routes to appropriate plugin)
jn profile info @namespace/name

# Discover profiles from URL
jn profile discover <url>
```

### Zig Discovery Changes

1. Check if plugin has `profiles` in modes
2. Query plugin for profile list
3. Cache profile metadata
4. Route `jn profile` commands to appropriate plugin

---

## Filesystem Profiles Still Supported

User-defined profiles in filesystem take precedence:

```
~/.local/jn/profiles/http/myapi/_meta.json    # Base config
~/.local/jn/profiles/http/myapi/users.json    # Endpoint

# This overrides any bundled @myapi/users from http plugin
```

Priority:
1. Project filesystem (`.jn/profiles/`)
2. User filesystem (`~/.local/jn/profiles/`)
3. Plugin bundled profiles
4. Plugin dynamic discovery

---

## Migration Path

1. **Phase 1**: Add `profiles` mode to plugin spec
2. **Phase 2**: Update http plugin with bundled profiles
3. **Phase 3**: Update duckdb plugin with dynamic discovery
4. **Phase 4**: Update `jn profile` to query plugins
5. **Phase 5**: Deprecate separate profile discovery code

---

## Summary

**Before**: Profiles are filesystem-only, discovered separately from plugins
**After**: Profiles are a plugin capability, discoverable via `--mode=profiles`

This unifies the plugin interface and enables:
- Dynamic profile discovery (DuckDB tables, API endpoints)
- Bundled profiles with plugins
- Language-agnostic profile providers
- Better introspection and documentation
