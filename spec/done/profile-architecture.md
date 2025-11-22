# Profile System Architecture

**Status:** ✅ Implemented
**Date:** 2025-11-22
**See also:** `profile-usage.md`, `profile-cli.md`

---

## Overview

The JN profile system provides **curated configurations** for data sources, APIs, and transformation tools. Profiles abstract connection details, standardize parameters, and make complex resources addressable with simple `@namespace/name` references.

**Key Insight:** Profiles curate, they don't just expose. A single API might have multiple profiles with different defaults for different use cases.

---

## What Profiles Are (and Aren't)

### Profiles ARE:

✅ **Curated configurations** - Pre-filled connection details and common parameters
✅ **Addressable resources** - `@genomoncology/alterations` instead of full URLs
✅ **Reusable templates** - DRY principle for repeated data access patterns
✅ **Environment-aware** - Use `${ENV_VAR}` for credentials and endpoints
✅ **Discoverable** - Listed via `jn profile list`, searchable, inspectable

### Profiles are NOT:

❌ **A data format** - Profiles configure how to access data, not how to store it
❌ **A plugin type** - Profiles are consumed by plugins (HTTP, DuckDB, MCP, etc.)
❌ **A replacement for plugins** - Plugins execute, profiles configure
❌ **One-to-one with APIs** - One API can have many profiles for different use cases

---

## Profile Types

JN supports profiles for different plugin types:

### 1. HTTP API Profiles

**Purpose:** Configure REST API endpoints with authentication and defaults

**Location:** `profiles/http/{namespace}/`

**Structure:**
```
profiles/http/genomoncology/
├── _meta.json           # Base URL, headers, auth
├── alterations.json     # Endpoint configuration
└── genes.json           # Another endpoint
```

**Use case:** Accessing RESTful APIs with consistent auth and parameter patterns

**Example:**
```bash
jn cat "@genomoncology/alterations?gene=BRAF"
# → GET https://api.genomoncology.io/api/alterations?gene=BRAF
```

### 2. DuckDB Query Profiles

**Purpose:** Named SQL queries against analytical databases

**Location:** `profiles/duckdb/{namespace}/`

**Structure:**
```
profiles/duckdb/analytics/
├── _meta.json           # Database path
├── sales-summary.sql    # Named query
└── by-region.sql        # Parameterized query
```

**Use case:** Reusable SQL queries with parameters

**Example:**
```bash
jn cat "@analytics/by-region?region=West"
# → SELECT ... FROM sales WHERE region = $region
```

### 3. MCP Server Profiles

**Purpose:** Configure Model Context Protocol servers and tools

**Location:** `profiles/mcp/{server}/`

**Structure:**
```
profiles/mcp/biomcp/
├── _meta.json           # Server command and transport
└── search.json          # Tool configuration
```

**Use case:** Accessing MCP tools with consistent parameters

**Example:**
```bash
jn cat "@biomcp/search?gene=EGFR&disease=lung%20cancer"
# → Calls biomcp search tool
```

### 4. Gmail Profiles

**Purpose:** Query Gmail with saved searches and filters

**Location:** `profiles/gmail/{account}/`

**Structure:**
```
profiles/gmail/work/
├── _meta.json           # OAuth credentials
└── inbox.json           # Inbox query config
```

**Use case:** Reading emails with pre-configured filters

**Example:**
```bash
jn cat "@gmail/work/inbox?from=boss"
# → Fetches inbox emails from boss
```

### 5. JQ Filter Profiles

**Purpose:** Reusable jq transformations

**Location:** `profiles/jq/{namespace}/`

**Structure:**
```
profiles/jq/builtin/
└── pivot.jq             # Pivot transformation
```

**Use case:** Complex transformations as named filters

**Example:**
```bash
jn cat data.csv | jn filter "@builtin/pivot" -p row=product -p col=month
```

---

## Profile Structure

### Meta File Pattern

Every profile namespace has a `_meta.json` file that defines connection configuration:

**HTTP Meta:**
```json
{
  "base_url": "https://${API_URL}/api",
  "headers": {
    "Authorization": "Token ${API_KEY}",
    "Accept": "application/json"
  },
  "timeout": 60
}
```

**DuckDB Meta:**
```json
{
  "driver": "duckdb",
  "path": "data/analytics.duckdb",
  "description": "Analytics database"
}
```

**MCP Meta:**
```json
{
  "command": "uv",
  "args": ["run", "--with", "biomcp-python", "biomcp", "run"],
  "transport": "stdio"
}
```

**Gmail Meta:**
```json
{
  "auth_type": "oauth2",
  "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
  "token_path": "~/.jn/gmail-token.json"
}
```

### Component Files

Individual components (endpoints, queries, tools) are defined in separate files:

**HTTP Endpoint (`alterations.json`):**
```json
{
  "path": "/alterations",
  "method": "GET",
  "type": "source",
  "params": ["gene", "mutation_type", "limit"],
  "description": "Genetic alterations database"
}
```

**DuckDB Query (`by-region.sql`):**
```sql
-- Regional sales analysis
-- Parameters: region

SELECT product, SUM(revenue) as total
FROM sales
WHERE region = $region
GROUP BY product;
```

**MCP Tool (`search.json`):**
```json
{
  "tool": "search",
  "defaults": {
    "limit": 10
  }
}
```

---

## Profile Discovery

### Discovery Mechanisms

JN discovers profiles through two mechanisms:

#### 1. Filesystem Scanning (HTTP, JQ, MCP, Gmail)

The framework scans `profiles/` directory for JSON files:
```
profiles/
├── http/*/          → Scans for *.json files
├── jq/*/            → Scans for *.jq files
├── mcp/*/           → Scans for _meta.json + tools
└── gmail/*/         → Scans for *.json files
```

**Pros:** Fast, simple, no subprocess overhead
**Cons:** Framework must know profile structure

#### 2. Plugin-Based Discovery (DuckDB, future databases)

The framework calls plugins with `--mode inspect-profiles`:
```bash
uv run --script duckdb_.py --mode inspect-profiles
# Returns NDJSON: {"reference": "@ns/q", "type": "duckdb", ...}
```

**Pros:** Self-contained, plugin owns profile logic
**Cons:** Subprocess overhead for discovery

### Discovery Priority

Profiles are discovered in this order:

1. **Project profiles:** `.jn/profiles/` (current working directory)
2. **User profiles:** `$JN_HOME/profiles/` or `~/.jn/profiles/`
3. **System profiles:** `jn_home/profiles/` (bundled with JN)

Project profiles override user profiles, which override system profiles.

---

## Profile Resolution

### Address Syntax

Profiles use `@namespace/component[?params]` syntax:

```bash
@genomoncology/alterations            # No parameters
@genomoncology/alterations?gene=BRAF  # With parameters
@analytics/by-region?region=West      # DuckDB query with param
```

### Resolution Process

```
User input: @genomoncology/alterations?gene=BRAF
     ↓
1. Parse address
   namespace = "genomoncology"
   component = "alterations"
   params = {"gene": "BRAF"}
     ↓
2. Find profile type
   Search: profiles/*/genomoncology/
   Found: profiles/http/genomoncology/
     ↓
3. Load meta file
   Read: profiles/http/genomoncology/_meta.json
   Extract: base_url, headers, auth
     ↓
4. Load component file
   Read: profiles/http/genomoncology/alterations.json
   Extract: path, method, params, defaults
     ↓
5. Merge configuration
   meta + component + query params
     ↓
6. Build final URL
   base_url + path + query string
   Result: https://api.genomoncology.io/api/alterations?gene=BRAF
     ↓
7. Execute
   HTTP plugin fetches data
     ↓
8. Stream NDJSON
   {"id": 1, "gene": "BRAF", ...}
```

---

## Self-Contained Protocol Plugins

### Architecture Pattern

**Problem:** How do plugins discover and resolve their own profiles?

**Solution:** Plugins implement `--mode inspect-profiles` and vendor all profile logic.

### Before (Coupled Architecture)

```
Framework (profiles/service.py)
├── _parse_http_profile()      # HTTP-specific logic
├── _parse_duckdb_profile()    # DuckDB-specific logic
├── _parse_mcp_profile()       # MCP-specific logic
└── list_all_profiles()        # Scans filesystem

Plugin (duckdb_.py)
└── reads()                    # Just executes queries
```

**Problems:**
- Framework contains plugin-specific code
- Can't add new database plugins without framework changes
- ~200 lines of DuckDB logic in framework

### After (Self-Contained Architecture)

```
Framework (profiles/service.py)
└── list_all_profiles()        # Calls plugins, aggregates results

Plugin (duckdb_.py)
├── inspect_profiles()         # Scans filesystem for .sql files
├── _load_profile()            # Parses .sql metadata
└── reads()                    # Executes queries

Communication:
Framework → subprocess: uv run --script plugin.py --mode inspect-profiles
Plugin → Framework: NDJSON stream of ProfileInfo records
```

**Benefits:**
✅ Framework is generic (no plugin-specific code)
✅ Plugin is standalone (testable independently)
✅ Easy to add PostgreSQL, MySQL plugins (same pattern)

### Implementation Pattern

**Plugin implements:**

```python
def inspect_profiles() -> Iterator[dict]:
    """List all available profiles for this plugin.

    Called by framework with --mode inspect-profiles.
    Returns ProfileInfo-compatible NDJSON records.
    """
    for profile_dir in _get_profile_paths():
        for namespace_dir in profile_dir.iterdir():
            # Scan profile files
            for profile_file in namespace_dir.glob("*.sql"):
                yield {
                    "reference": f"@{namespace}/{name}",
                    "type": "duckdb",
                    "namespace": namespace,
                    "name": name,
                    "path": str(profile_file),
                    "description": description,
                    "params": params,
                    "examples": []
                }
```

**Framework calls:**

```python
# Discover all plugins
plugins = get_cached_plugins_with_fallback(...)

# Call each plugin to discover profiles
for plugin in plugins.values():
    process = subprocess.Popen(
        ["uv", "run", "--script", str(plugin.path), "--mode", "inspect-profiles"],
        stdout=subprocess.PIPE,
        text=True
    )
    stdout, _ = process.communicate()

    for line in stdout.strip().split("\n"):
        profile_info = json.loads(line)
        profiles.append(ProfileInfo(**profile_info))
```

---

## Profile CLI

The profile CLI enables discovery and inspection:

### Commands

```bash
# List all profiles
jn profile list

# Filter by type
jn profile list --type duckdb

# Search profiles
jn profile search "sales"

# Show profile details
jn profile info "@analytics/sales-summary"

# Tree view
jn profile tree

# Tree for specific namespace
jn profile tree http/genomoncology
```

### Output Formats

**Text (human-readable):**
```bash
$ jn profile list --type duckdb

DuckDB Query Profiles:
  @analytics/sales-summary    Sales summary report
  @analytics/by-region        Regional sales analysis
  @test/all-users             All users
  @test/by-id                 User by ID
```

**JSON (agent-consumable):**
```bash
$ jn profile list --type duckdb --format json
{
  "@analytics/sales-summary": {
    "type": "duckdb",
    "namespace": "analytics",
    "name": "sales-summary",
    "path": "/path/to/sales-summary.sql",
    "description": "Sales summary report",
    "params": []
  },
  ...
}
```

**See:** `spec/done/profile-cli.md` for full CLI documentation

---

## Environment Variables

Profiles support environment variable substitution:

### Syntax

Use `${VAR_NAME}` in meta files:

```json
{
  "base_url": "https://${GENOMONCOLOGY_URL}/api",
  "headers": {
    "Authorization": "Token ${GENOMONCOLOGY_API_KEY}"
  }
}
```

### Resolution

Variables are resolved at runtime:
```bash
export GENOMONCOLOGY_URL="api.genomoncology.io"
export GENOMONCOLOGY_API_KEY="secret123"

jn cat "@genomoncology/alterations"
# Resolves to: https://api.genomoncology.io/api/alterations
# With header: Authorization: Token secret123
```

### Security

- Never store credentials in profile files
- Use environment variables for secrets
- Profile files can be committed to version control
- Credentials stay in local environment

---

## Use Cases

### 1. API Access

**Before profiles:**
```bash
curl -H "Authorization: Token $API_KEY" \
     "https://$API_URL/api/alterations?gene=BRAF&limit=10" \
  | jq -c '.results[]'
```

**With profiles:**
```bash
jn cat "@genomoncology/alterations?gene=BRAF&limit=10"
```

### 2. Database Queries

**Before profiles:**
```bash
duckdb analytics.duckdb << 'EOF' | jq -R 'split("|") | {product: .[0], revenue: .[1]}'
SELECT product, SUM(revenue)
FROM sales
WHERE region = 'West'
GROUP BY product;
EOF
```

**With profiles:**
```bash
jn cat "@analytics/by-region?region=West"
```

### 3. Data Pipelines

**Profiles in pipelines:**
```bash
# ETL: Extract from API, Transform, Load to database
jn cat "@genomoncology/alterations?gene=BRAF" | \
  jn filter "@builtin/extract-fields" -p fields=gene,name,type | \
  jn put "@warehouse/alterations"
```

**Multi-source aggregation:**
```bash
# Combine data from multiple APIs
jn cat "@genomoncology/alterations?gene=BRAF" > braf-go.ndjson &
jn cat "@oncokb/annotations?gene=BRAF" > braf-oncokb.ndjson &
wait
cat braf-*.ndjson | jn filter "@builtin/merge-by-key" -p key=name | jn put output.csv
```

---

## Testing and Validation

### Profile Discovery

```bash
# Verify profile is discovered
jn profile list --type duckdb | grep "@analytics/sales-summary"

# Check profile details
jn profile info "@analytics/sales-summary"
```

### Profile Execution

```bash
# Test without parameters
jn cat "@analytics/sales-summary" --limit 1

# Test with parameters
jn cat "@analytics/by-region?region=West" --limit 1

# Check output format
jn cat "@analytics/sales-summary" | jq -c '.[0] | keys'
```

### Environment Variables

```bash
# Check which env vars are needed
jn profile info "@genomoncology/alterations" | grep -A5 "Environment"

# Verify env vars are set
echo $GENOMONCOLOGY_URL
echo $GENOMONCOLOGY_API_KEY

# Test with missing env var
unset GENOMONCOLOGY_API_KEY
jn cat "@genomoncology/alterations"
# Should error with clear message about missing env var
```

---

## Best Practices

### 1. Organize by Domain

```
profiles/
├── http/
│   ├── genomoncology/    # Genomic oncology API
│   ├── clinicaltrials/   # Clinical trials API
│   └── pubmed/           # PubMed API
└── duckdb/
    ├── analytics/        # Business analytics queries
    ├── research/         # Research data queries
    └── reports/          # Report queries
```

### 2. Use Descriptive Names

**Good:**
```
@genomoncology/alterations-by-gene
@analytics/monthly-revenue-by-region
@reports/top-selling-products
```

**Bad:**
```
@go/alt
@data/query1
@reports/report
```

### 3. Document Parameters

**In SQL files:**
```sql
-- Regional sales analysis
-- Parameters: region (required), year (optional)
-- Example: jn cat "@analytics/by-region?region=West&year=2024"

SELECT ...
```

**In JSON files:**
```json
{
  "path": "/alterations",
  "params": ["gene", "mutation_type", "limit"],
  "description": "Query alterations by gene and mutation type"
}
```

### 4. Version Control

**Commit to version control:**
- ✅ Profile files (JSON, SQL)
- ✅ Meta files (with `${ENV_VAR}` placeholders)
- ✅ Documentation

**DO NOT commit:**
- ❌ Credentials (use env vars)
- ❌ API keys (use env vars)
- ❌ Database files (use relative paths)

### 5. Test Before Committing

```bash
# Verify profile is discovered
make test-profiles

# Test execution
jn cat "@namespace/profile" --limit 1

# Check for env var leaks
grep -r "secret\|password\|token" profiles/
```

---

## Summary

The JN profile system provides:

✅ **Addressable resources** - `@namespace/name` syntax
✅ **Curated configurations** - Pre-filled defaults and parameters
✅ **Environment-aware** - `${ENV_VAR}` substitution for credentials
✅ **Discoverable** - `jn profile list`, search, inspect
✅ **Reusable** - DRY principle for data access patterns
✅ **Self-contained** - Protocol plugins vendor their own profile logic
✅ **Hierarchical** - Namespace organization by domain
✅ **Secure** - Credentials via environment, not files

**Result:** Complex APIs and databases become simple, addressable resources that agents can discover and use with minimal configuration.
