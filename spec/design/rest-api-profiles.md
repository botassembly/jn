# REST API Profiles - Design

## Overview

Reusable API configurations that provide clean `@profile/path` syntax for accessing endpoints. Profiles centralize authentication, base URLs, and common parameters, enabling teams to work with APIs efficiently.

## Why Profiles?

**Problem:** Repeating URLs and auth headers is error-prone and exposes credentials.

```bash
# Before profiles - repetitive and insecure
jn cat https://api.${GENOMONCOLOGY_URL}/api/alterations \
  --headers '{"Authorization": "Token ${GENOMONCOLOGY_API_KEY}"}'
```

**Solution:** Configure once, use everywhere.

```bash
# With profile - clean and safe
jn cat @genomoncology/alterations
```

**Benefits:**
- **One-time setup:** Configure API once
- **Clean syntax:** Readable commands
- **Credential safety:** Tokens in env vars, not command history
- **Team sharing:** Commit profiles to `.jn/profiles/`
- **OpenAPI import:** Auto-generate from Swagger specs

## Core Concepts

### Profiles as Sources

Profiles define **sources** - endpoints that fetch data:

```json
{
  "base_url": "https://api.${GENOMONCOLOGY_URL}/api",
  "sources": {
    "alterations": {
      "path": "/alterations",
      "method": "GET",
      "description": "Genetic alterations database"
    },
    "annotations_match": {
      "path": "/annotations/match",
      "method": "POST",
      "description": "Batch variant matching"
    }
  }
}
```

**Source** = URL + method + optional filters/transforms

### Sources + Filters = Pipelines

```bash
# Source alone
jn cat @genomoncology/alterations

# Source + filter (still a source conceptually)
jn cat @genomoncology/alterations | jn filter '.gene == "BRAF"'

# Source + filter + filter + target
jn cat @genomoncology/alterations | \
  jn filter '.gene == "BRAF"' | \
  jn filter '{name, mutation_type}' | \
  jn put results.csv
```

## Profile Structure

### Basic Profile

```json
{
  "base_url": "https://api.${GENOMONCOLOGY_URL}/api",
  "headers": {
    "Authorization": "Token ${GENOMONCOLOGY_API_KEY}",
    "Accept": "application/json"
  },
  "timeout": 60
}
```

**Location hierarchy** (first found wins):
1. Project: `.jn/profiles/http/`
2. User: `~/.local/jn/profiles/http/`
3. Bundled: `jn_home/profiles/http/`

### Advanced Profile with Sources

```json
{
  "base_url": "https://api.${GENOMONCOLOGY_URL}/api",
  "headers": {
    "Authorization": "Token ${GENOMONCOLOGY_API_KEY}"
  },
  "sources": {
    "alterations": {
      "path": "/alterations",
      "method": "GET",
      "params": ["gene", "mutation_type"],
      "description": "Query genetic alterations"
    },
    "clinical_trials": {
      "path": "/clinical_trials",
      "method": "GET",
      "params": ["disease", "alteration"],
      "description": "Search clinical trials"
    }
  }
}
```

**Usage:**
```bash
# Basic source
jn cat @genomoncology/alterations

# With parameters
jn cat @genomoncology/alterations?gene=BRAF&mutation_type=Missense

# Named source
jn cat @genomoncology:alterations
```

### Hierarchical Profiles (Large APIs)

For APIs with many endpoints, use hierarchical structure:

```
genomoncology/
├── _profile.json          # Base config (URL, auth)
├── alterations.json       # Alterations endpoints
├── annotations.json       # Annotations endpoints
├── clinical_trials.json   # Clinical trials
└── filters/
    ├── pivot-transcripts.jq
    └── extract-hgvs.jq
```

**`_profile.json` (base):**
```json
{
  "base_url": "https://api.${GENOMONCOLOGY_URL}/api",
  "headers": {
    "Authorization": "Token ${GENOMONCOLOGY_API_KEY}"
  }
}
```

**`alterations.json`:**
```json
{
  "sources": {
    "list": {
      "path": "/alterations",
      "method": "GET"
    },
    "detail": {
      "path": "/alterations/{id}",
      "method": "GET"
    }
  }
}
```

**Usage:**
```bash
jn cat @genomoncology/alterations:list
jn cat @genomoncology/alterations:detail --id "BRAF V600E"
```

## Environment Variable Substitution

**Syntax:** `${VAR_NAME}`

**Example:**
```json
{
  "base_url": "https://api.${GENOMONCOLOGY_URL}/api",
  "headers": {
    "Authorization": "Token ${GENOMONCOLOGY_API_KEY}"
  }
}
```

**Resolution:**
```bash
export GENOMONCOLOGY_URL="genomoncology.io"
export GENOMONCOLOGY_API_KEY="abc123"

# Resolves to:
# base_url: https://api.genomoncology.io/api
# Authorization: Token abc123
```

**Error handling:** If variable not set, raise clear error message.

## OpenAPI/Swagger Integration

### Auto-Generate from OpenAPI Spec

```bash
# Generate profile from OpenAPI/Swagger
jn profile generate genomoncology \
  --from-openapi https://api.${GENOMONCOLOGY_URL}/api/schema

# Creates: ~/.local/jn/profiles/http/genomoncology/
# - _profile.json (base config)
# - alterations.json (alterations endpoints)
# - annotations.json (annotations endpoints)
# - etc.
```

### OpenAPI Mapping

**OpenAPI auth → JN profile:**

| OpenAPI Scheme | JN Profile Config |
|----------------|-------------------|
| `bearerAuth` | `{"Authorization": "Bearer ${TOKEN}"}` |
| `apiKey` (header) | `{"{key-name}": "${VAR}"}` |
| `apiKey` (query) | `params: {"{key}": "${VAR}"}` |
| `http` (basic) | `auth: {"type": "basic", "username": "${USER}", "password": "${PASS}"}` |
| `oauth2` | `auth: {"type": "oauth2", "token_url": "...", "token": "${TOKEN}"}` |

**OpenAPI paths → Sources:**
```yaml
# OpenAPI
paths:
  /alterations:
    get:
      operationId: listAlterations
      summary: List genetic alterations
```

**→ JN Profile:**
```json
{
  "sources": {
    "alterations": {
      "path": "/alterations",
      "method": "GET",
      "description": "List genetic alterations"
    }
  }
}
```

### Schema Inference from Examples

For APIs without OpenAPI specs, infer schemas from examples:

```bash
# Collect examples
jn cat @genomoncology/alterations | head -n 100 > examples.jsonl

# Infer schema
jn profile infer-schema genomoncology/alterations \
  --from-examples examples.jsonl

# Creates JSON schema for validation (future feature)
```

## Path Variables

**Template syntax:** `{variable}`

```json
{
  "sources": {
    "user_detail": {
      "path": "/users/{id}",
      "method": "GET"
    }
  }
}
```

**Usage:**
```bash
# Option 1: Positional (if path has one variable)
jn cat @api/users/123

# Option 2: Named (explicit)
jn cat @api/users:user_detail --id 123

# Option 3: Path substitution
jn cat "@api/users/{id}" --id 123
```

## Methods: GET vs POST

### GET Sources

```json
{
  "sources": {
    "list_users": {
      "path": "/users",
      "method": "GET",
      "params": ["limit", "offset"]
    }
  }
}
```

**Usage:**
```bash
jn cat @api/users?limit=10&offset=20
```

### POST Sources

```json
{
  "sources": {
    "match_annotations": {
      "path": "/annotations/match",
      "method": "POST",
      "content_type": "application/x-www-form-urlencoded",
      "description": "Batch variant matching"
    }
  }
}
```

**Usage:**
```bash
# POST body from stdin
echo 'batch=chr7|140453136|A|T|GRCh37' | \
  jn cat @genomoncology:match_annotations --method POST
```

## Source-Specific Filters

Some filters only make sense for specific sources. Profiles can include these:

```json
{
  "sources": {
    "annotations": {
      "path": "/annotations",
      "method": "GET",
      "filters": {
        "pivot-transcripts": {
          "description": "Pivot to one row per transcript",
          "filter": "@genomoncology/filters/pivot-transcripts"
        }
      }
    }
  }
}
```

**Usage:**
```bash
# Apply source-specific filter
jn cat @genomoncology/annotations | \
  jn filter '@genomoncology/annotations:pivot-transcripts'
```

**Why:** Annotations have complex nested structure. The pivot filter is only meaningful for annotations, not alterations or clinical trials.

## Risks & Challenges

### 1. Profile Name Collisions
**Risk:** Two profiles with same name.

**Mitigation:**
- Clear precedence: project > user > bundled
- `jn profile info <name>` shows which loaded
- Warning if overridden

### 2. Environment Variable Missing
**Risk:** `${GENOMONCOLOGY_API_KEY}` undefined.

**Mitigation:**
- Raise error with helpful message
- Show which variable missing
- Document required env vars in profile metadata

### 3. Path Ambiguity
**Risk:** `/users/123` could be path or variable.

**Mitigation:**
- Require `{id}` syntax for variables
- Plain `/users/123` is literal path

### 4. Token Exposure
**Risk:** Tokens logged in command history.

**Mitigation:**
- Never put tokens in commands
- Use `${VAR}` in profiles
- Document security best practices

### 5. Profile Portability
**Risk:** Profiles with hardcoded URLs/tokens.

**Mitigation:**
- Require env vars for secrets
- Support `${VAR}` for all sensitive fields
- Lint profiles for hardcoded credentials

### 6. Hierarchical Confusion
**Risk:** Too many levels → hard to navigate.

**Mitigation:**
- Max 3 levels recommended
- Clear naming conventions
- `jn profile list` shows structure

### 7. Auth Token Rotation
**Risk:** Tokens expire, OAuth refresh needed.

**Mitigation:**
- Phase 1: Manual token refresh
- Phase 2: OAuth refresh flow support
- Document token lifecycle

### 8. Schema Validation
**Risk:** Invalid requests due to schema changes.

**Mitigation:**
- Phase 1: No validation (fail fast from API)
- Phase 2: Optional JSON schema validation
- OpenAPI generation includes schemas

## Open Questions

### 1. Automatic Token Refresh?
Should profiles handle OAuth token refresh?

**Trade-off:** Convenience vs. complexity and security.

**Recommendation:** Phase 2. Start with manual tokens.

### 2. Profile Versioning?
Should profiles track API versions?

**Example:**
```json
{
  "api_version": "v2",
  "base_url": "https://api.example.com/v2"
}
```

**Trade-off:** Useful but adds complexity.

**Recommendation:** Add if needed. Most APIs version via URL.

### 3. Caching?
Should profile responses cache?

**Trade-off:** Performance vs. stale data.

**Recommendation:** Phase 2. Let users cache manually with files.

### 4. Response Transformation?
Should profiles define response transforms?

**Example:**
```json
{
  "sources": {
    "users": {
      "path": "/users",
      "transform": ".results[] | {id, name}"
    }
  }
}
```

**Trade-off:** Powerful but couples profile to response format.

**Recommendation:** Keep separate. Use filters explicitly.

## Related Documents

- `http-design.md` - HTTP plugin implementation
- `genomoncology-api.md` - Real-world example with sources/filters
- `format-design.md` - Format plugins and tables

## Next Steps

1. **Implement hierarchical profiles** - `_profile.json` inheritance
2. **OpenAPI generator** - Auto-create profiles from Swagger
3. **Schema inference** - Learn schemas from examples (genson)
4. **Source-specific filters** - Tie filters to API endpoints
5. **Profile validation** - Lint for security issues
