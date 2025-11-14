# JN Profile System

**Purpose:** Define how profiles curate APIs, MCPs, and data sources
**Status:** Implementation guide
**Date:** 2025-11-12
**See also:** `spec/design/addressability.md`

---

## What Are Profiles?

Profiles are **curated configurations** for data sources and targets. They abstract connection details, pre-fill common parameters, and define which fields matter for specific use cases.

**Key concept:** Profiles curate APIs/MCPs, they don't just expose them. A single API endpoint might have multiple profiles with different pre-filled values for different use cases.

---

## Profile Structure

### Directory Layout

```
profiles/
├── http/                     # HTTP API profiles
│   └── {api}/
│       ├── _meta.json        # Connection config
│       ├── {source}.json     # Source profile
│       ├── {target}.json     # Target profile
│       └── filters/          # Profile-specific adapters (optional)
│           └── {name}.jq
│
├── mcp/                      # MCP server profiles
│   └── {server}/
│       ├── _meta.json        # Server config
│       └── {tool}.json       # Tool profile
│
└── gmail/                    # Gmail profiles
    ├── _meta.json            # Auth config
    └── {source}.json         # Source profile
```

**Pattern:** `profiles/{plugin}/{profile}/{component}.json`
- `{plugin}` - Plugin type (http, mcp, gmail, s3)
- `{profile}` - Profile namespace (genomoncology, biomcp, mycompany)
- `{component}` - Source or target name (alterations, search, inbox)

---

## Meta File: `_meta.json`

The meta file contains **connection configuration** for the entire profile namespace. The plugin defines what fields are required.

### HTTP Plugin Meta

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

**Fields:**
- `base_url` - API base URL (with env var substitution)
- `headers` - HTTP headers (auth, content-type, etc.)
- `timeout` - Request timeout in seconds

### MCP Plugin Meta

```json
{
  "command": "uv",
  "args": ["run", "--with", "biomcp-python", "biomcp", "run"],
  "description": "BioMCP: Biomedical Model Context Protocol",
  "transport": "stdio"
}
```

**Fields:**
- `command` - Executable to run MCP server
- `args` - Command arguments
- `transport` - Communication protocol (stdio, http)
- `description` - Human-readable description

### Gmail Plugin Meta

```json
{
  "auth_type": "oauth2",
  "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
  "token_path": "~/.jn/gmail-token.json",
  "credentials_path": "~/.jn/gmail-credentials.json"
}
```

**Fields:**
- `auth_type` - Authentication method
- `scopes` - OAuth2 scopes
- `token_path` - Where to store access token
- `credentials_path` - Where to find client credentials

**Note:** Each plugin defines its own meta schema. The framework passes the entire meta dict to the plugin.

---

## Component Files: Sources and Targets

Component files define **individual sources or targets**. The filename is the component name.

### Source Profile

A source is a **readable data stream** with optional pre-filled parameters.

**Example:** `profiles/http/genomoncology/alterations.json`

```json
{
  "type": "source",
  "path": "/alterations",
  "method": "GET",
  "params": ["gene", "mutation_type", "biomarker", "page", "limit"],
  "description": "Genetic alterations database"
}
```

**Fields:**
- `type` - "source" or "target"
- `path` - API endpoint path (relative to base_url)
- `method` - HTTP method (GET, POST, PUT, PATCH, DELETE)
- `params` - Available parameters (optional, for documentation)
- `description` - What this source provides

**Usage:**
```bash
jn cat "@genomoncology/alterations?gene=BRAF&limit=10"
```

### Source with Pre-Filled Values

**Example:** `profiles/http/genomoncology/braf-trials.json`

```json
{
  "type": "source",
  "path": "/trials",
  "method": "GET",
  "defaults": {
    "gene": "BRAF",
    "status": "Recruiting"
  },
  "params": ["disease", "age_min", "age_max"],
  "description": "Recruiting clinical trials for BRAF mutations"
}
```

**Fields:**
- `defaults` - Pre-filled parameter values

**Usage:**
```bash
# Pre-filled: gene=BRAF, status=Recruiting
jn cat "@genomoncology/braf-trials?disease=melanoma"

# Can override defaults
jn cat "@genomoncology/braf-trials?gene=EGFR&status=Active"
```

**Why pre-fill?** Common use cases become one-liners. Same endpoint, different curated profiles.

### Source with Adapter

**Example:** `profiles/http/genomoncology/annotations-flat.json`

```json
{
  "type": "source",
  "path": "/annotations",
  "method": "GET",
  "adapter": "filters/flatten-transcripts.jq",
  "description": "Annotations with flattened transcript structure"
}
```

**Fields:**
- `adapter` - JQ filter to transform output (relative to profile directory)

**Adapter file:** `profiles/http/genomoncology/filters/flatten-transcripts.jq`

```jq
# Flatten nested transcript arrays
.[] | .transcripts[] | {
  gene: .gene,
  transcript: .id,
  consequence: .consequence
}
```

**Usage:**
```bash
jn cat "@genomoncology/annotations-flat"
# 1. Fetches /annotations
# 2. Runs through flatten-transcripts.jq filter
# 3. Outputs flattened NDJSON
```

**Why adapters?** APIs return complex nested structures. Adapters normalize to simple NDJSON.

### Target Profile

A target is a **writable destination** with optional validation and formatting.

**Example:** `profiles/http/warehouse/analyses.json`

```json
{
  "type": "target",
  "path": "/analyses",
  "method": "POST",
  "adapter": "filters/validate-schema.jq",
  "required_fields": ["patient_id", "gene", "variant"],
  "description": "Upload analysis results"
}
```

**Fields:**
- `type` - "target"
- `method` - Usually POST, PUT, or PATCH
- `adapter` - Filter to run BEFORE sending (validation/formatting)
- `required_fields` - Fields that must be present

**Usage:**
```bash
jn cat data.json | jn put "@warehouse/analyses"
# 1. Reads NDJSON from stdin
# 2. Runs through validate-schema.jq
# 3. Checks required_fields present
# 4. POSTs to /analyses endpoint
```

### MCP Tool Profile

**Example:** `profiles/mcp/biomcp/search.json`

```json
{
  "tool": "search",
  "description": "Search biomedical resources",
  "parameters": {
    "gene": {
      "type": "string",
      "description": "Gene symbol (e.g., BRAF, TP53)"
    },
    "disease": {
      "type": "string",
      "description": "Disease or condition name"
    },
    "variant": {
      "type": "string",
      "description": "Specific variant notation"
    }
  }
}
```

**Fields:**
- `tool` - MCP tool name
- `parameters` - Tool parameter schema (from MCP spec)

**Usage:**
```bash
jn cat "@biomcp/search?gene=BRAF&disease=melanoma"
```

### MCP Tool with Pre-Filled Values

**Example:** `profiles/mcp/biomcp/braf-trials.json`

```json
{
  "tool": "trial_search",
  "defaults": {
    "gene": "BRAF",
    "status": "recruiting"
  },
  "parameters": {
    "disease": {
      "type": "string",
      "description": "Disease or condition"
    }
  },
  "description": "Recruiting trials for BRAF mutations"
}
```

**Usage:**
```bash
jn cat "@biomcp/braf-trials?disease=melanoma"
# Calls trial_search with gene=BRAF, status=recruiting, disease=melanoma
```

---

## How Profiles Are Used

### Addressing Syntax

**Format:** `@profile/component[?params]`

```bash
# HTTP API profile
jn cat "@genomoncology/alterations?gene=BRAF&limit=10"

# MCP tool profile
jn cat "@biomcp/search?gene=EGFR&disease=lung%20cancer"

# Gmail profile
jn cat "@gmail/inbox?from=boss&newer_than=7d"

# Target profile
jn cat data.json | jn put "@warehouse/analyses"
```

### Resolution Process

```
@genomoncology/alterations?gene=BRAF
  ↓
1. Find plugin: genomoncology → profiles/http/genomoncology/
  ↓
2. Load meta: profiles/http/genomoncology/_meta.json
  ↓
3. Load component: profiles/http/genomoncology/alterations.json
  ↓
4. Merge meta + component config
  ↓
5. Apply defaults from component
  ↓
6. Add query parameters
  ↓
7. Build URL: base_url + path + query
   Result: https://api.genomoncology.io/api/alterations?gene=BRAF
  ↓
8. Execute: HTTP plugin fetches data
  ↓
9. Apply adapter (if defined)
  ↓
10. Output NDJSON
```

### Parameter Behavior

**Parameters go to BOTH profile and plugin:**
- Profile uses for API query
- Plugin uses for formatting/config

**Example:**
```bash
jn cat "@api/source?limit=100&indent=2"
# Profile: Uses limit=100 in API call
# Plugin: Uses indent=2 for JSON formatting
# Both receive the same parameters
```

### Defaults vs Parameters

**Merge order:**
1. Component `defaults` (lowest priority)
2. Query string parameters (override defaults)

**Example:**
```json
// Profile: braf-trials.json
{
  "defaults": {
    "gene": "BRAF",
    "status": "Recruiting"
  }
}
```

```bash
# Uses defaults
jn cat "@genomoncology/braf-trials?disease=melanoma"
# → gene=BRAF, status=Recruiting, disease=melanoma

# Override defaults
jn cat "@genomoncology/braf-trials?gene=EGFR&status=Active"
# → gene=EGFR, status=Active
```

---

## Assessment of Existing Profiles

### HTTP Profiles

**Location:** `jn_home/profiles/http/genomoncology/`

**What's good:**
- Clear separation: `_meta.json` for connection, individual files for endpoints
- Environment variable substitution working
- Parameter lists documented

**What needs fixing:**
- GenomOncology is experimental, not bundled - **move to experiments/jn_home/**
- No adapters defined yet, but structure supports them
- Some profiles list params but don't validate or use them
- Missing `defaults` field in profiles that could benefit (e.g., trial status filters)
- No target profiles defined yet (all are sources)

### MCP Profiles

**Location:** `jn_home/profiles/mcp/{biomcp,context7,desktop-commander}/`

**What's good:**
- Meta file correctly specifies how to launch MCP server
- Tool names match MCP spec
- Parameter schemas documented

**What needs fixing:**
- No pre-filled defaults examples (could create braf-search.json with gene=BRAF)
- No adapters defined (MCP output could benefit from normalization)
- Parameter schemas duplicated from MCP spec (could auto-generate these)
- Missing description fields in some tool profiles

### Gmail Profiles

**Location:** `jn_home/profiles/gmail/`

**What's good:**
- OAuth2 configuration clear
- Multiple curated sources (inbox, sent, starred, etc.)
- Defaults field used correctly (e.g., inbox has `"in": "inbox"`)
- Parameter lists documented

**What needs fixing:**
- Examples still use old `-p` syntax instead of query strings
- No adapters defined (email normalization would be useful)
- Starred/unread could be better as filters on messages, not separate sources
- Missing target profiles (composing/sending email)
- Token/credentials paths hardcoded (should support env var override)

---

## Design Principles

### Plugin Defines Meta Schema

Each plugin defines what fields belong in `_meta.json`. The framework doesn't enforce a schema - it passes the entire dict to the plugin.

**Why:** Different protocols need different connection configs. HTTP needs base_url/headers, MCP needs command/args, S3 needs bucket/region, etc.

### Component Name = Filename

The component name comes from the filename, not from JSON content. This prevents sync issues.

**Good:** `profiles/http/myapi/users.json` → component name is `users`
**Bad:** Having a `"name": "users"` field inside the JSON

### Pre-Filled Values for Curation

The `defaults` field lets you create multiple profiles from the same endpoint with different pre-filled values.

**Example use cases:**
- Enum values: ascending-sort.json vs descending-sort.json
- Type discrimination: customers.json vs invoices.json (for APIs that use type field)
- Common filters: braf-trials.json vs egfr-trials.json

### Adapters Stay Close

Adapters/filters belong in `{profile}/filters/` directory, not in a separate top-level location.

**Why:** Keeps profile self-contained. Moving a profile moves its adapters too.

**Structure:**
```
profiles/http/genomoncology/
├── _meta.json
├── alterations.json
├── annotations.json
└── filters/
    ├── flatten-transcripts.jq
    └── normalize-dates.jq
```

### Parameters Are Flexible

The `params` list is documentation, not validation. Unlisted parameters still work (pass-through to API).

**Why:** APIs change, new parameters added. Don't break on unexpected params.

---

## Future Work (Not in This Document)

- Profile discovery CLI commands (`jn profile list/info/test`)
- OpenAPI generation (create profiles from Swagger specs)
- Profile validation (check required fields, env vars exist)
- Schema diff (detect API changes)
- Auto-completion for profile parameters

These topics belong in separate design documents.
