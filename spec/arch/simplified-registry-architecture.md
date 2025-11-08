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

---

## Addendum: Migration Impact Analysis

**Status**: Architecture proposal - not yet implemented
**Last Updated**: 2025-11-08

This section analyzes which existing architecture documents are compatible with this new approach vs. which would need updates if we proceed with implementation.

### Documents Using OLD Approach (4-concept registry)

These documents reference the current `sources`/`converters`/`targets`/`pipelines` structure and would need updates:

#### **architecture.md** - ⚠️ CORE ARCHITECTURE - Major changes needed
- **Current state**: References `sources`, `converters`, `targets`, `pipelines` throughout
- **Config structure**: Shows 4 separate registry sections
- **API examples**: `config.add_source()`, `config.add_converter()`, `config.add_target()`, `config.add_pipeline()`
- **Gap**: Entire mental model based on 4-concept architecture
- **Migration effort**: HIGH - Complete rewrite needed

#### **user-guide.md** - ⚠️ Major changes needed
- **Current state**: Shows `jn.json` with 4-section structure
- **Commands**: `jn new source`, `jn new converter`, `jn new target`, `jn new pipeline`
- **Workflow**: `jn list sources/pipelines`, `jn show source`, `jn explain demo`
- **Gap**: Entire user workflow based on old registry structure
- **Migration effort**: HIGH - New workflow examples needed

#### **pipeline-arguments.md** - ⚠️ Major changes needed
- **Current state**: All examples reference `pipelines` with parameterization
- **Config examples**: Shows `source`, `converter`, `target` fields in pipeline configs
- **Gap**: In new approach, standalone pipeline files are optional; might just use `jn run <filter>` instead
- **Migration effort**: MEDIUM - Either update for optional pipeline files, or remove if too complex for MVP

#### **adapters.md** - ⚠️ Moderate changes needed
- **Current state**: Has config examples with `sources`, `converters`, `targets`, `pipelines` sections
- **Valid concepts**: "Source adapters" and "Target adapters" remain valid (format boundary handlers)
- **Gap**: Config JSON examples need updating, but adapter *concepts* are unchanged
- **Migration effort**: MEDIUM - Update config examples; keep conceptual content

#### **drivers.md** - ⚠️ Minor changes needed
- **Current state**: References sources/targets in example configs
- **Valid concepts**: Driver types (exec, shell, curl, file, mcp) unchanged
- **Gap**: Just example JSON configs need updating; driver concepts unchanged
- **Migration effort**: LOW - Update JSON examples only

#### **unix-integration.md** - ⚠️ Minor updates needed
- **Current state**: Uses both approaches in examples
  - Old: `jn run process.json --input-file` (pipeline files)
  - New: `jn cat`, `jn put` (neutral commands)
- **Gap**: Examples using `jn run pipeline.json` should show both old (pipeline files) and new (filter names) approaches
- **Migration effort**: LOW - Add alternative examples with new commands

#### **aggregations-and-pivots.md** - ⚠️ Very minor update
- **Current state**: Mostly neutral jq patterns
- **Gap**: One mention of "converters" in rationale ("users need jq for converters anyway")
- **Migration effort**: VERY LOW - Change one word: "converters" → "filters"

---

### Documents Using NEW Approach

#### **simplified-registry-architecture.md** (this document) - ✅ The new spec
- Defines `apis` + `filters` approach
- Commands: `jn new api`, `jn new filter`, `jn cat`, `jn run`, `jn put`
- Smart URL matching, auto-detection
- **This IS the new approach specification**

---

### Documents That Are NEUTRAL (Work with both approaches)

These documents are intentionally registry-agnostic and require NO changes:

#### **cat-command.md** - ✅ Clean
- **Purpose**: Exploration command `jn cat <source>`
- **Content**: Auto-detection logic (URL/file/command)
- **Assessment**: Doesn't reference registry structure at all; works perfectly in both worlds

#### **put-command.md** - ✅ Clean
- **Purpose**: Write command `jn put <target>`
- **Content**: Format auto-detection from extension
- **Assessment**: Doesn't reference registry structure; works perfectly in both worlds

#### **shape-command.md** - ✅ Clean
- **Purpose**: Analyze NDJSON with `jn shape`
- **Content**: Schema inference, samples, stats
- **Note**: One mention of "pipelines" in "use case" context, not structural
- **Assessment**: Completely neutral

#### **adapter-excel.md** - ✅ Clean
- **Purpose**: Excel format specification (.xlsx, multi-sheet)
- **Content**: Pure format handling, streaming approach
- **Assessment**: No registry references; completely neutral

#### **adapter-markdown.md** - ✅ Clean
- **Purpose**: Markdown format specification (with Front Matter)
- **Content**: Pure format handling, block types
- **Assessment**: No registry references; completely neutral

---

### Command Mapping: Old → New

If this architecture is adopted, here's how commands would change:

| Old Approach | New Approach | Notes |
|--------------|--------------|-------|
| `jn new source <name>` | `jn new api <name>` | Or `jn api add <name>` if inverted |
| `jn new converter <name>` | `jn new filter <name>` | Or `jn filter add <name>` if inverted |
| `jn new target <name>` | Uses same `apis` registry | Same API, different default method |
| `jn new pipeline <name>` | Optional, or just shell pipes | Standalone pipeline files become optional |
| `jn list sources` | `jn list apis` | Or `jn api list` if inverted |
| `jn list converters` | `jn list filters` | Or `jn filter list` if inverted |
| `jn run pipeline-name` | `jn run filter-name` | Or `jn cat \| jn run filter \| jn put` |
| `jn show source <name>` | `jn show api <name>` | Or `jn api show <name>` if inverted |
| `jn cat <source>` | **No change** ✅ | Same in both approaches |
| `jn put <target>` | **No change** ✅ | Same in both approaches |
| `jn shape` | **No change** ✅ | Same in both approaches |

---

### Config Structure Comparison

#### Old Approach (Current)
```json
{
  "sources": {
    "github-users": {
      "driver": "curl",
      "curl": {
        "method": "GET",
        "url": "https://api.github.com/users",
        "headers": {"Accept": "application/vnd.github.v3+json"}
      }
    }
  },
  "converters": {
    "filter-high": {
      "expr": "select(.amount > 100)"
    }
  },
  "targets": {
    "file-out": {
      "driver": "file",
      "file": {"path": "output.json", "mode": "write"}
    }
  },
  "pipelines": {
    "demo": {
      "steps": ["source:github-users", "converter:filter-high", "target:file-out"]
    }
  }
}
```

#### New Approach (Proposed)
```json
{
  "apis": {
    "github": {
      "base_url": "https://api.github.com",
      "auth": {"type": "bearer", "token": "${env:GITHUB_TOKEN}"},
      "headers": {"Accept": "application/vnd.github.v3+json"},
      "source_method": "GET",
      "target_method": "POST"
    }
  },
  "filters": {
    "high-value": {
      "query": "select(.amount > 1000)"
    }
  }
}
```

**Usage shift:**
```bash
# Old: Explicit pipeline
jn run demo

# New: Composable commands
jn cat github:/users | jn run high-value | jn put output.json
```

---

### Migration Strategy Summary

| Document | Priority | Migration Effort | Changes Needed |
|----------|----------|------------------|----------------|
| **architecture.md** | HIGH | HIGH | Complete rewrite - core mental model changes |
| **user-guide.md** | HIGH | HIGH | New workflow examples with `apis`/`filters` |
| **pipeline-arguments.md** | MEDIUM | MEDIUM | Update for optional pipeline files, or defer |
| **adapters.md** | MEDIUM | MEDIUM | Update config examples; keep adapter concepts |
| **drivers.md** | LOW | LOW | Update JSON examples only |
| **unix-integration.md** | LOW | LOW | Add alternative examples with new commands |
| **aggregations-and-pivots.md** | VERY LOW | VERY LOW | Change "converters" → "filters" (1 word) |
| **cat-command.md** | N/A | NONE | ✅ No changes needed |
| **put-command.md** | N/A | NONE | ✅ No changes needed |
| **shape-command.md** | N/A | NONE | ✅ No changes needed |
| **adapter-excel.md** | N/A | NONE | ✅ No changes needed |
| **adapter-markdown.md** | N/A | NONE | ✅ No changes needed |

---

### Key Insight

**The newer specifications (cat, put, shape, format adapters, aggregations, Unix integration) are already compatible with the new approach.** They were designed to be registry-agnostic. Only the older foundational documents (architecture, user-guide, pipeline-arguments) are tightly coupled to the 4-concept model.

This suggests a **phased migration approach**:
1. **Phase 1**: Keep current architecture, continue building cat/put/shape/adapters
2. **Phase 2**: Implement new registry structure alongside old (feature flag)
3. **Phase 3**: Update core docs (architecture, user-guide) to new approach
4. **Phase 4**: Deprecate old structure, default to new approach

The good news: **Much of the recent design work is future-proof** and will work seamlessly with either architecture.
