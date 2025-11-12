# JN Profiles System

**Purpose:** Define how profiles curate APIs, MCPs, and data sources with sources, targets, and adapters
**Related:** addressability.md
**Date:** 2025-11-12

---

## What I Found

After reviewing the codebase and existing design documents, here's what's been done:

### ✅ What's Working
- **Hierarchical structure:** `_meta.json` + source files (Gmail, MCP, HTTP all use this)
- **Query string parameters:** `@api/source?key=value` fully implemented
- **Environment variables:** `${VAR}` substitution working
- **Parameter validation:** Warns about unsupported params
- **Three profile types:** HTTP, Gmail, MCP all have working implementations

### ⚠️ What's Inconsistent
- **Three competing documents:** openapi-integration-ideas.md, profile-query-strings.md, rest-api-profiles.md
- **Multiple syntaxes proposed:** `@api/source`, `@api:source`, `@api/source:subsource` (only first works)
- **Source-focused:** Profiles mostly for reading, target/writing concept underdeveloped
- **Filter/adapter concept unclear:** Mentioned but not well-defined

### ❌ What's Missing
- **Target profiles:** No clear design for write destinations with adapters
- **CLI curation commands:** No `jn profile` commands for management
- **Enum-based source differentiation:** Can't create multiple sources from same endpoint with different enum values
- **Source/target adapters:** No clear implementation of baked-in transformations

---

## Profile Concepts (Clarified)

### Source
**Definition:** A readable data stream with optional pre-processing

```json
{
  "type": "source",
  "description": "Clinical trials for BRAF mutations",
  "endpoint": "/trials",
  "defaults": {
    "gene": "BRAF",
    "status": "Recruiting"
  },
  "adapter": "@filters/normalize-trials"
}
```

**Usage:**
```bash
jn cat "@genomoncology/braf-trials"
# Fetches /trials?gene=BRAF&status=Recruiting
# Runs through normalize-trials filter
# Outputs NDJSON
```

**Key point:** Source = endpoint + default params + adapter (optional)

### Target
**Definition:** A writable destination with optional post-processing

```json
{
  "type": "target",
  "description": "Upload to analysis database",
  "endpoint": "/analyses",
  "method": "POST",
  "adapter": "@filters/format-for-db",
  "required_fields": ["patient_id", "gene", "variant"]
}
```

**Usage:**
```bash
jn cat data.json | jn put "@warehouse/analyses"
# Runs through format-for-db filter
# POSTs to /analyses endpoint
# Returns confirmation
```

**Key point:** Target = adapter (optional) + endpoint + validation

### Adapter
**Definition:** A transformation that prepares data for source consumption or target ingestion

**Two types:**
1. **Source adapter** - Normalizes/cleans data after fetching
2. **Target adapter** - Formats/validates data before writing

```json
{
  "adapter": "@biomcp/normalize-variants",
  "description": "Convert MCP variant format to JN standard schema"
}
```

---

## Profile Structure

### Basic Profile (Single File)
```
profiles/http/simple-api.json
```

```json
{
  "base_url": "https://api.example.com",
  "headers": {
    "Authorization": "Bearer ${API_TOKEN}"
  },
  "path": "/data",
  "method": "GET"
}
```

Usage: `jn cat "@simple-api"`

### Hierarchical Profile (Multiple Sources)
```
profiles/http/genomoncology/
├── _meta.json          # Connection config
├── alterations.json    # Source: genetic alterations
├── trials.json         # Source: clinical trials
├── braf-trials.json    # Source: BRAF-specific trials (enum differentiation)
└── results.json        # Target: upload results
```

**_meta.json:**
```json
{
  "base_url": "https://api.genomoncology.io",
  "headers": {
    "Authorization": "Token ${GENOMONCOLOGY_KEY}"
  },
  "timeout": 60
}
```

**trials.json (generic source):**
```json
{
  "type": "source",
  "path": "/trials",
  "params": ["gene", "status", "disease"]
}
```

**braf-trials.json (enum-differentiated source):**
```json
{
  "type": "source",
  "path": "/trials",
  "defaults": {
    "gene": "BRAF",
    "status": "Recruiting"
  },
  "description": "Recruiting trials for BRAF mutations"
}
```

Usage:
```bash
jn cat "@genomoncology/trials?gene=EGFR"        # Generic
jn cat "@genomoncology/braf-trials"             # Pre-configured for BRAF
```

**Key point:** Same endpoint, different defaults = different curated sources

### Profile with Adapters
```json
{
  "type": "source",
  "path": "/annotations",
  "adapter": "@genomoncology/flatten-transcripts",
  "description": "Annotations with flattened transcript structure"
}
```

Usage:
```bash
jn cat "@genomoncology/annotations"
# 1. Fetches from /annotations
# 2. Runs through flatten-transcripts filter
# 3. Outputs normalized NDJSON
```

Adapter file: `profiles/jq/genomoncology/flatten-transcripts.jq`

### Target Profile
```json
{
  "type": "target",
  "path": "/analyses",
  "method": "POST",
  "adapter": "@warehouse/validate-schema",
  "required_fields": ["patient_id", "gene", "variant"],
  "description": "Upload analysis results to warehouse"
}
```

Usage:
```bash
jn cat data.json | jn put "@warehouse/analyses"
# 1. Runs data through validate-schema filter
# 2. Checks required_fields present
# 3. POSTs to /analyses endpoint
```

---

## Enum-Based Source Differentiation

**Problem:** API has endpoint `/trials` with status enum: `Recruiting|Active|Completed`

**Without differentiation:**
```bash
jn cat "@genomoncology/trials?status=Recruiting"
jn cat "@genomoncology/trials?status=Active"
jn cat "@genomoncology/trials?status=Completed"
```

**With differentiation (curated sources):**
```
profiles/http/genomoncology/
├── trials-recruiting.json
├── trials-active.json
└── trials-completed.json
```

Each file:
```json
{
  "type": "source",
  "path": "/trials",
  "defaults": {
    "status": "Recruiting"  // or "Active" or "Completed"
  },
  "description": "Recruiting clinical trials"
}
```

Usage:
```bash
jn cat "@genomoncology/trials-recruiting"
jn cat "@genomoncology/trials-active"
jn cat "@genomoncology/trials-completed"
```

**Key insight:** Profiles curate common use cases, not just expose raw API

---

## Plugin Functions

Plugins should have 2-4 functions for profile operations:

### HTTP Plugin Functions
```python
def reads(url, headers, config):
    """Read from HTTP endpoint (source)"""

def writes(url, headers, data, config):
    """Write to HTTP endpoint (target)"""

def list_sources(profile_dir):
    """List available sources in profile"""

def list_targets(profile_dir):
    """List available targets in profile"""
```

### MCP Plugin Functions
```python
def reads(server, tool, params):
    """Call MCP tool and stream results (source)"""

def writes(server, tool, data, params):
    """Send data to MCP tool (target)"""

def list_tools(server):
    """List available MCP tools"""
```

**Key point:** 2 core functions (reads/writes) + 2 optional helper functions (list/discover)

---

## CLI Commands for Profile Management

### Core Commands

**List profiles:**
```bash
jn profile list                      # All profiles
jn profile list --type http          # Only HTTP profiles
jn profile list genomoncology        # Sources/targets in genomoncology
```

**Show profile info:**
```bash
jn profile info @genomoncology/alterations
# Shows: type, path, params, defaults, adapter, examples
```

**Test profile:**
```bash
jn profile test @genomoncology/alterations?gene=BRAF
# Makes request, shows: status, response time, sample data
```

**Create profile:**
```bash
jn profile create myapi \
  --base-url https://api.example.com \
  --auth-header "Authorization: Bearer ${TOKEN}"

# Creates: profiles/http/myapi/_meta.json
```

**Add source to profile:**
```bash
jn profile add-source myapi/users \
  --path /users \
  --params "limit,offset" \
  --description "List all users"

# Creates: profiles/http/myapi/users.json
```

**Add target to profile:**
```bash
jn profile add-target myapi/results \
  --path /results \
  --method POST \
  --adapter @myapi/validate \
  --required "patient_id,gene"

# Creates: profiles/http/myapi/results.json (type: target)
```

**Generate from OpenAPI:**
```bash
jn profile generate genomoncology \
  --from-openapi https://api.genomoncology.io/schema \
  --sources "alterations,annotations,trials"

# Creates hierarchical profile with selected endpoints
```

**Edit profile:**
```bash
jn profile edit @genomoncology/alterations
# Opens in $EDITOR
# OR
jn profile set @genomoncology/alterations --default gene=BRAF
# Programmatic edit
```

### Advanced Commands

**Diff profiles:**
```bash
jn profile diff @genomoncology/alterations \
  --from v1.0 \
  --to v2.0
# Shows parameter changes, deprecations
```

**Validate profile:**
```bash
jn profile validate @genomoncology/alterations
# Checks: required fields, env vars exist, schema valid
```

**Clone profile:**
```bash
jn profile clone @genomoncology/trials @genomoncology/braf-trials
jn profile set @genomoncology/braf-trials --default gene=BRAF
```

---

## OpenAPI Integration

### Selective Generation

**Problem:** APIs have hundreds of endpoints, generating all creates noise

**Solution:** Generate only what you need

```bash
# Generate specific endpoints
jn profile generate genomoncology \
  --from-openapi https://api.genomoncology.io/schema \
  --sources "alterations,annotations,trials"

# Interactive selection
jn profile browse genomoncology \
  --from-openapi https://api.genomoncology.io/schema
# Shows checklist, pick with arrow keys/space
```

### Hierarchical Sub-Endpoints

For APIs with logical grouping:

```
genomoncology/
├── _meta.json
├── alterations.json              # GET /alterations
├── alterations/
│   ├── suggest.json              # GET /alterations/suggest
│   └── validate.json             # GET /alterations/validate
├── annotations.json              # GET /annotations
└── annotations/
    └── match.json                # POST /annotations/match
```

Usage:
```bash
jn cat "@genomoncology/alterations"              # Main
jn cat "@genomoncology/alterations/suggest"      # Sub-endpoint
```

### Lazy Loading

```bash
jn cat "@genomoncology/alterations/suggest?gene=BRAF"

# First time:
# → "Endpoint not found. Generate from OpenAPI? [Y/n]"
# → Generates alterations/suggest.json
# → Executes request

# Subsequent:
# → Just works
```

---

## Profile Resolution Algorithm

```
Input: @genomoncology/alterations?gene=BRAF
  ↓
1. Parse reference
   - API: genomoncology
   - Source: alterations
   - Params: {gene: "BRAF"}
  ↓
2. Load hierarchical profile
   - Load: profiles/http/genomoncology/_meta.json
   - Load: profiles/http/genomoncology/alterations.json
   - Merge: _meta + source config
  ↓
3. Apply defaults and params
   - Profile defaults: {}
   - User params: {gene: "BRAF"}
   - Final params: {gene: "BRAF"}
  ↓
4. Build URL
   - Base: https://api.genomoncology.io
   - Path: /alterations
   - Query: ?gene=BRAF
   - Result: https://api.genomoncology.io/alterations?gene=BRAF
  ↓
5. Apply source adapter (if defined)
   - Run fetched data through adapter filter
  ↓
6. Output NDJSON
```

---

## Two Design Documents

### 1. addressability.md ✅
**Focus:** How to address files, URLs, protocols, profiles, stdin/stdout
**Status:** Complete

### 2. profiles.md (this document) ✅
**Focus:** How profiles curate APIs with sources, targets, adapters
**Status:** This document

**Together they define:**
- Addressability: Universal syntax for all data sources
- Profiles: Curation layer on top of APIs/protocols

---

## Migration Plan

### Keep
- ✅ Hierarchical structure (_meta.json + sources)
- ✅ Query string syntax (`?key=value`)
- ✅ Environment variable substitution
- ✅ Parameter validation
- ✅ Working HTTP, Gmail, MCP profiles

### Remove
- ❌ rest-api-profiles.md (redundant with this doc)
- ❌ openapi-integration-ideas.md (consolidate here)
- ❌ profile-query-strings.md (already implemented, now documented here)

### Add
- 🆕 Target profile concept (type: target)
- 🆕 Source/target adapter system
- 🆕 CLI profile management commands
- 🆕 Enum-based source differentiation

---

## Summary

**Profiles curate APIs, not just expose them:**

- **Sources** - Pre-configured endpoints for reading (with optional adapters)
- **Targets** - Pre-configured endpoints for writing (with optional adapters)
- **Adapters** - Transformations baked into source/target profiles
- **Enum differentiation** - Multiple sources from same endpoint with different defaults
- **Hierarchical structure** - _meta.json + source files (already working)
- **CLI management** - Commands for creating, editing, testing profiles
- **OpenAPI integration** - Selective generation, not dump 227 files

**The result:** Curated, reusable, agent-friendly data access patterns.
