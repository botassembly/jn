# Simplified Registry Architecture

## Problem Statement

**Current architecture is too complex**:
- Four concepts: sources, filters, targets, pipelines
- Indirection: Named references require lookup
- Over-engineered: Storing things that could be auto-detected (file formats, shell commands)

**Pure standalone files have drawbacks**:
- Duplication of complex API configs (base URLs, auth, defaults)
- No way to reuse sophisticated configurations
- Lose benefits of a registry for truly reusable components

## Proposed Solution: Hybrid Registry

**Central registry for complex, reusable configs**:
- ✅ APIs (with auth, base URLs, default methods)
- ✅ Filters (JQ transformation logic)

**Auto-detection for simple things**:
- ❌ File formats (CSV, JSON, Excel) - adapters handle this
- ❌ Shell commands - JC handles this
- ❌ URLs without auth - just pass them directly

**Standalone pipeline files for workflows**:
- ✅ Can reference registry items
- ✅ Can define inline
- ✅ Composable with pipes

## Registry Structure

### New jn.json Format

```json
{
  "apis": {
    "github": {
      "base_url": "https://api.github.com",
      "auth": {
        "type": "bearer",
        "token": "${env:GITHUB_TOKEN}"
      },
      "headers": {
        "Accept": "application/vnd.github.v3+json"
      },
      "source_method": "GET",
      "target_method": "POST"
    },
    "internal-api": {
      "base_url": "https://api.mycompany.com",
      "auth": {
        "type": "bearer",
        "token": "${env:INTERNAL_API_KEY}"
      },
      "source_method": "GET",
      "target_method": "POST"
    }
  },
  "filters": {
    "high-value": {
      "query": "select(.amount > 1000)"
    },
    "aggregate-by-category": {
      "query": "group_by(.category) | map({\n  category: .[0].category,\n  total: map(.amount) | add,\n  count: length\n})"
    },
    "flatten-nested": {
      "query": ".items[] | {id, name, email: .contact.email}"
    }
  }
}
```

**Key changes**:
1. Just two sections: `apis` and `filters`
2. APIs are generic (can be source OR target)
3. Default methods can be overridden
4. Environment variable substitution: `${env:VAR_NAME}`

### Additional API Types

**Databases**:
```json
{
  "apis": {
    "warehouse": {
      "type": "postgres",
      "host": "localhost",
      "port": 5432,
      "database": "analytics",
      "auth": {
        "user": "etl_user",
        "password": "${env:DB_PASSWORD}"
      }
    }
  }
}
```

**Cloud Storage**:
```json
{
  "apis": {
    "s3-data": {
      "type": "s3",
      "bucket": "my-data-bucket",
      "region": "us-east-1",
      "auth": {
        "access_key": "${env:AWS_ACCESS_KEY}",
        "secret_key": "${env:AWS_SECRET_KEY}"
      }
    }
  }
}
```

**Message Queues**:
```json
{
  "apis": {
    "kafka-events": {
      "type": "kafka",
      "brokers": ["localhost:9092"],
      "topic": "user-events",
      "consumer_group": "jn-processor"
    }
  }
}
```

**GraphQL**:
```json
{
  "apis": {
    "github-graphql": {
      "type": "graphql",
      "endpoint": "https://api.github.com/graphql",
      "auth": {"type": "bearer", "token": "${env:GITHUB_TOKEN}"}
    }
  }
}
```

## Registration Commands

Manage APIs and filters in the registry:

```bash
# Register new API
jn new api github \
  --base-url https://api.github.com \
  --auth bearer \
  --token-env GITHUB_TOKEN

# Register new filter
jn new filter high-value --query 'select(.amount > 1000)'

# List registered items
jn list apis
jn list filters

# Show details
jn show api github
jn show filter high-value

# Edit (opens in $EDITOR)
jn edit api github
jn edit filter high-value

# Remove
jn remove api github
jn remove filter high-value
```

## How It Works

### Use Case 1: Simple File Transform

**No registry needed** - just use direct commands:

```bash
# File formats auto-detected
jn cat data.csv | jq 'select(.amount > 100)' | jn put output.xlsx
```

### Use Case 2: Reusable Filter

**Reference filter from registry**:

```bash
# Use named filter
jn cat data.csv | jn run high-value | jn put output.json
```

Behind the scenes:
1. `jn run high-value` looks up filter in registry
2. Reads NDJSON from stdin
3. Applies jq query: `select(.amount > 1000)`
4. Writes NDJSON to stdout

### Use Case 3: API with Auth

**URL matching against registry**:

```bash
# Pass URL directly
jn cat https://api.github.com/users/octocat/repos | jn put repos.json
```

Behind the scenes:
1. `jn cat` sees URL starts with `https://api.github.com`
2. Matches against registry entry `github`
3. Automatically adds bearer token from `$GITHUB_TOKEN`
4. Adds `Accept` header
5. Makes GET request (default `source_method`)

**Or explicit**:

```bash
# Explicitly reference API by name
jn cat github:/users/octocat/repos | jn put repos.json
```

### Use Case 4: Post to API

```bash
# Send data to API
jn cat users.csv | jn put https://api.mycompany.com/users/bulk
```

Behind the scenes:
1. `jn put` sees URL matches `internal-api` registry entry
2. Uses POST method (default `target_method`)
3. Adds auth token from environment
4. Sends NDJSON as request body

### Use Case 5: Override API Method

```bash
# Override default POST to use PUT
jn cat user.json | jn put https://api.mycompany.com/users/123 --method PUT
```

### Use Case 6: Path as Argument

**API config with path parameter**:

```json
{
  "apis": {
    "product-api": {
      "base_url": "https://api.shop.com",
      "paths": {
        "get_product": "/products/${product_id}",
        "list_products": "/products"
      },
      "auth": {"type": "bearer", "token": "${env:API_KEY}"}
    }
  }
}
```

**Usage**:

```bash
# Use path template
jn cat product-api:get_product --product-id 12345 | jn put product.json

# Or direct URL (still uses auth)
jn cat https://api.shop.com/products/12345 | jn put product.json
```

## Smart URL Matching

**Longest prefix match**:

Registry has:
- `https://api.github.com` → github config
- `https://api.github.com/v4/graphql` → github-graphql config (different auth)

User runs:
```bash
jn cat https://api.github.com/v4/graphql/query
```

Matches: `github-graphql` (longer prefix wins)

## Input Detection

`jn run` can accept input in multiple ways:

### 1. File Path

```bash
jn run filter-name --input data.csv
jn run filter-name --input /path/to/data.json
```

Auto-detects format from extension.

### 2. URL

```bash
jn run filter-name --input https://api.example.com/data
```

Checks registry for matching API config.

### 3. stdin (pipe)

```bash
jn cat source | jn run filter-name | jn put target
```

Default when no `--input` specified.

### 4. Inline JSON

```bash
jn run filter-name --input '{"name": "Alice", "age": 30}'
jn run filter-name --input '[{"id": 1}, {"id": 2}]'
```

Detected by first character: `{` or `[`

## Simplified Commands

### `jn run <filter-name>`

Runs a named filter from registry.

```bash
# Input from stdin, output to stdout
jn cat data.csv | jn run high-value | jn put output.json

# Specify input/output
jn run high-value --input data.csv --output filtered.json

# Chain filters
jn cat data.csv | jn run filter1 | jn run filter2 | jn put output.json
```

### `jn cat <source>`

Extract data to NDJSON.

**Auto-detection**:
- File path → file adapter
- URL → curl adapter (with API registry lookup)
- Command → exec adapter (via JC)

```bash
# File
jn cat data.csv

# URL (matches registry)
jn cat https://api.github.com/users

# API by name
jn cat github:/users

# Command
jn cat "ls -la"
```

### `jn put <target>`

Load NDJSON to target.

**Auto-detection**:
- File path → file writer
- URL → HTTP POST (with API registry lookup)

```bash
# File
jn cat data.json | jn put output.csv

# URL (matches registry, uses POST)
jn cat data.json | jn put https://api.example.com/bulk-upload

# Override method
jn cat data.json | jn put https://api.example.com/users/123 --method PUT
```

## What Gets Removed

### ❌ Sources Section

**Before**:
```json
{
  "sources": {
    "github-users": {
      "driver": "curl",
      "url": "https://api.github.com/users",
      "headers": {...}
    }
  }
}
```

**After**: Just use `apis` registry
```json
{
  "apis": {
    "github": {
      "base_url": "https://api.github.com",
      "auth": {...}
    }
  }
}
```

### ❌ Filters Section (formerly "Converters")

**Before**:
```json
{
  "converters": {
    "filter-high": {
      "driver": "jq",
      "query": "select(.amount > 100)"
    }
  }
}
```

**After**: Renamed to `filters`, removed redundant driver
```json
{
  "filters": {
    "high-value": {
      "query": "select(.amount > 100)"
    }
  }
}
```

**Key change**: Following jq terminology, we call these "filters" not "converters". No need for `driver: "jq"` - that's the only option.

### ❌ Targets Section

**Before**: Separate from sources

**After**: Same `apis` registry, different default method

### ❌ Pipelines Section

**Before**: Centralized pipeline definitions

**After**: Standalone pipeline files or just use pipes

## Standalone Pipeline Files

You can still create pipeline files that reference registry:

**filter-and-save.json**:
```json
{
  "input": "${input_file}",
  "filter": "high-value",
  "output": "${output_file}"
}
```

**Usage**:
```bash
jn run filter-and-save.json --input-file data.csv --output-file out.json
```

Or inline:
```json
{
  "input": "https://api.github.com/users",
  "filter": {
    "query": "map({login, id, url})"
  },
  "output": "users.json"
}
```

## Benefits of This Approach

### ✅ Simple Things Stay Simple

```bash
# No config needed
jn cat data.csv | jq 'select(.valid)' | jn put output.json
```

### ✅ Complex Things Are Manageable

```json
// Registry handles complexity
{
  "apis": {
    "internal": {
      "base_url": "https://api.internal.com",
      "auth": {"type": "oauth2", "token": "${env:TOKEN}"},
      "retry": {"max_attempts": 3, "backoff": "exponential"}
    }
  }
}
```

```bash
# Usage is still simple
jn cat internal:/data/feed | jn run transform | jn put output.json
```

### ✅ No Duplication for Reusables

APIs and filters defined once, used everywhere.

### ✅ Composable

```bash
# Mix registry and inline
jn cat github:/repos | jq 'select(.stars > 1000)' | jn run format-report | jn put report.xlsx
```

### ✅ Incremental Adoption

Start simple, add to registry only when needed.

## Migration Path

### Phase 1: Keep Current Architecture (jn.json with sources/filters/targets)
Status: Already implemented

### Phase 2: Simplify to apis + filters
- Migrate sources + targets → `apis` (unified)
- Rename converters → `filters` (following jq terminology)
- Remove driver specifications where redundant

### Phase 3: Add Smart Features
- URL matching for auto-config
- Inline JSON detection
- Path templates with arguments

### Phase 4: Standalone Pipeline Files
- Optional pipeline files that reference registry
- Composable with pipes

## Model Context Protocol (MCP)

**Status**: Separate but related

MCP servers could be treated as a special type of API:

```json
{
  "mcp": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/files"],
      "env": {}
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${env:GITHUB_TOKEN}"
      }
    }
  }
}
```

**Decision**: Keep MCP separate from `apis` initially. MCP has different semantics (tools, resources, prompts) than REST/GraphQL APIs. May merge later if patterns converge.

## Open Questions

### 1. API Registry Scope

**Option A**: Per-project (`.jn/config.json`)
```
project/
  .jn/
    config.json   # APIs and filters for this project
  data/
  pipelines/
```

**Option B**: Global + per-project
```
~/.jn/config.json        # Global APIs/filters
project/.jn/config.json  # Project-specific overrides
```

**Recommendation**: Start with per-project, add global later if needed.

### 2. Filter Syntax

**Option A**: Just jq string
```json
{
  "filters": {
    "high-value": "select(.amount > 1000)"
  }
}
```

**Option B**: Object with query
```json
{
  "filters": {
    "high-value": {
      "query": "select(.amount > 1000)"
    }
  }
}
```

**Recommendation**: Option B - allows future extensions (description, examples, etc.)

### 3. Pipeline Files

**Should they exist at all?**

**Arguments for**: Complex workflows benefit from declarative config
**Arguments against**: Just use shell scripts to chain commands

**Recommendation**: Make optional. Start with just commands + registry, add pipeline files later if users want them.

## Examples

### Example 1: Daily GitHub Report

**Registry** (.jn/config.json):
```json
{
  "apis": {
    "github": {
      "base_url": "https://api.github.com",
      "auth": {"type": "bearer", "token": "${env:GITHUB_TOKEN}"}
    }
  },
  "filters": {
    "popular-repos": "map(select(.stargazers_count > 100) | {name, stars: .stargazers_count, url})"
  }
}
```

**Script**:
```bash
#!/bin/bash
jn cat github:/orgs/myorg/repos | \
  jn run popular-repos | \
  jn put daily-report-$(date +%Y-%m-%d).xlsx
```

### Example 2: ETL Pipeline

```bash
# Extract from API
jn cat internal-api:/data/exports/latest | \
  # Transform with saved filter
  jn run cleanse-and-validate | \
  # Inline filter
  jq 'select(.valid == true)' | \
  # Aggregate with saved filter
  jn run aggregate-by-region | \
  # Load to database
  jn put postgres://localhost/warehouse/daily_stats
```

### Example 3: Multi-Source Aggregation

```bash
# Combine multiple sources
(
  jn cat api1:/sales | jq '. + {source: "api1"}'
  jn cat api2:/transactions | jq '. + {source: "api2"}'
  jn cat local-data.csv | jq '. + {source: "local"}'
) | jn run normalize-schema | \
  jn run aggregate-all | \
  jn put combined-report.xlsx
```

## Success Criteria

- [x] Simpler mental model (2 concepts vs 4)
- [x] Auto-detection reduces configuration
- [x] Complex configs (APIs with auth) remain manageable
- [x] No duplication for reusables
- [x] Composable with Unix pipes
- [x] Backward compatible migration path

## Potential Enhancements (Under Consideration)

### 1. Command Structure Inversion

**Current design**:
```bash
jn new api github
jn list apis
jn show api github
jn remove api github
```

**Alternative** (noun-first, like git):
```bash
jn api add github
jn api list
jn api show github
jn api remove github

jn filter add high-value
jn filter list
jn filter show high-value
```

**Benefits**:
- More intuitive grouping (all `api` commands together)
- Familiar to git users (`git remote add`, `git remote list`)
- Easier to discover: `jn api --help` shows all API commands

**Consideration**: This is mostly a style preference. Either works.

---

### 2. Smart Input Auto-Detection

**Idea**: When piping to `jn run`, automatically detect input type without explicit flags.

**Input could be**:
1. File paths (one per line)
2. URLs (starting with http://, https://)
3. API names (registry lookups)
4. MCP tool names
5. Inline JSON objects/arrays
6. NDJSON stream

**Example**:
```bash
# Pipe file paths (auto-detected as paths, not JSON)
echo -e "./data1.csv\n./data2.csv\n./data3.csv" | jn run filter-name

# Auto-processes each file without xargs:
# - Reads ./data1.csv → applies filter → outputs NDJSON
# - Reads ./data2.csv → applies filter → outputs NDJSON
# - Reads ./data3.csv → applies filter → outputs NDJSON
```

**Detection logic**:
```python
def detect_input_type(line):
    if line.startswith('{') or line.startswith('['):
        return 'json'
    elif line.startswith('http://') or line.startswith('https://'):
        return 'url'
    elif line in registry['apis']:
        return 'api_name'
    elif os.path.exists(line):
        return 'file_path'
    else:
        return 'string'
```

**Built-in xargs mode**:
```bash
# Instead of:
jn cat ls ./inbox/ | jq -r '.filename' | \
  xargs -I {} jn cat ./inbox/{} | jn run filter

# Just do:
jn cat ls ./inbox/ | jq -r '.filename' | jn run filter --each
```

The `--each` flag means: "Treat each line as a separate input, process it, emit results."

**Benefits**:
- No need for xargs boilerplate
- Natural for processing file lists
- Works with API names, URLs, file paths

**Trade-offs**:
- Ambiguity: Is `"users.csv"` a file path or JSON string?
- Magic behavior might be confusing
- Harder to debug

**Recommendation**: Start without this. Add `--each` mode later if users request it.

---

### 3. Implicit stdin/stdout

**Current design**: Explicit `-` for stdin/stdout
```bash
jn run filter.json --input - --output -
```

**Alternative**: Auto-detect when piped
```bash
# If stdin is a pipe, use it automatically
jn cat data.csv | jn run filter

# If stdout is a pipe, output there automatically
jn run filter | jn put output.csv
```

**When to use stdin**:
- stdin is a pipe (not a TTY)
- No `--input` specified

**When to use stdout**:
- stdout is a pipe (not a TTY)
- No `--output` specified

**Benefits**:
- Less typing
- More intuitive for pipe workflows
- Matches Unix conventions

**Trade-offs**:
- Might surprise users who expect explicit behavior
- Need to handle edge cases (redirects, process substitution)

**Recommendation**: Implement this. It aligns with Unix philosophy and reduces verbosity.

---

### 4. Stream of File Paths Processing

**Use case**: You have a list of file paths and want to process each one.

**Without quality-of-life features**:
```bash
jn cat ls ./inbox/ | jq -r '.filename' | while read file; do
  jn cat "./inbox/$file" | jn run filter | jn put "./output/$file"
done
```

**With `--each` mode**:
```bash
jn cat ls ./inbox/ | jq -r '.filename' | \
  jn run filter --each --input-prefix ./inbox/ --output-prefix ./output/
```

**How it works**:
1. Reads file paths from stdin (one per line)
2. For each path: `jn cat {input-prefix}/{path}`
3. Applies filter
4. Writes to: `jn put {output-prefix}/{path}`

**Alternative**: Use `jn cat` in batch mode
```bash
jn cat ./inbox/*.csv | jn run filter | jn put ./output/combined.json
```

This processes all files, concatenates NDJSON streams, applies filter once.

**Benefits**:
- Eliminates shell loops
- Faster (single process)
- Simpler syntax

**Trade-offs**:
- More magic
- Harder to understand what's happening
- Edge cases (what if path has special chars?)

**Recommendation**: Start simple. Users can use shell loops or xargs. Add `--each` only if there's strong demand.

---

### 5. Multi-Input Auto-Detection

**Use case**: You want to process multiple types of inputs in one command.

**Example**:
```bash
# Mix file paths, URLs, and API names
echo -e "./local.csv\nhttps://api.example.com/data\ngithub:/users" | jn run filter
```

**Behavior**:
- Auto-detects each line type
- Fetches data accordingly
- Concatenates NDJSON streams
- Applies filter to combined stream

**Benefits**:
- Very flexible
- Handles heterogeneous inputs naturally

**Trade-offs**:
- Complex implementation
- Surprising behavior
- Hard to reason about

**Recommendation**: Don't implement. Too much magic. Users can combine manually:
```bash
(
  jn cat ./local.csv
  jn cat https://api.example.com/data
  jn cat github:/users
) | jn run filter
```

---

## Summary of Potential Enhancements

| Enhancement | Priority | Recommendation |
|-------------|----------|----------------|
| Command structure inversion (`jn api add`) | Medium | Consider for consistency |
| Smart input auto-detection | Low | Too complex, defer |
| Implicit stdin/stdout | High | Implement - matches Unix conventions |
| `--each` mode for file lists | Low | Defer - users can use xargs/loops |
| Multi-input auto-detection | Very Low | Don't implement - too magical |

**Core principle**: Keep simple things simple. Don't add features that make common cases more complex to support rare edge cases.

## Recommendation

**Implement this hybrid approach**:
1. Simplify registry to `apis` + `filters`
2. Add smart URL matching
3. Keep commands simple (cat, run, put)
4. Make pipeline files optional

This gives the best of both worlds: simplicity for common cases, power for complex scenarios.
