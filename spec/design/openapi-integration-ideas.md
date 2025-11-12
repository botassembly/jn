# OpenAPI/Swagger Integration for JN

## The Reality Check

I fetched the actual GenomOncology OpenAPI spec. Here's what we're dealing with:

**The Numbers:**
- **227 endpoints** total
- We currently use **6 endpoints** (2.6%)
- Auto-generating everything = **227 JSON files** ❌

**The Mapping Problem:**

OpenAPI paths don't map cleanly to our profile names:

```
OpenAPI Path                              Our Current Name        Auto-Generated Name
/api/alterations/                      →  alterations.json        alterations.json ✓
/api/trials/                           →  clinical_trials.json    trials.json ✗
/api/annotations/match                 →  (doesn't exist yet)     annotations_match.json
/api/alterations/suggest               →  (doesn't exist)         alterations_suggest.json
/api/users/{pk}/alert_configs          →  (doesn't exist)         users_pk_alert_configs.json ✗
```

**Natural Grouping:**

The API has logical clusters:
- `users/` (27 endpoints)
- `annotations/` (20 endpoints)
- `cases/` (18 endpoints)
- `trials/` (17 endpoints)
- `therapies/` (12 endpoints)
- `alterations/` (9 endpoints)

## Solution: Hierarchical + Selective

Generate a hierarchical structure that mirrors the API, but **only for endpoints you actually use**:

```
genomoncology/
├── _meta.json
├── alterations.json              # GET /api/alterations/
├── alterations/                  # Sub-endpoints (generated on-demand)
│   ├── actionability.json        # GET /api/alterations/actionability
│   ├── suggest.json              # GET /api/alterations/suggest
│   └── validate.json             # GET /api/alterations/validate
├── annotations.json              # GET /api/annotations/
├── annotations/
│   └── match.json                # POST /api/annotations/match (we use this!)
├── trials.json                   # GET /api/trials/ (note: was clinical_trials!)
└── trials/
    ├── matches.json              # POST /api/trials/matches
    └── suggest.json              # GET /api/trials/suggest
```

**Usage:**
```bash
# Main endpoints (current behavior)
jn cat @genomoncology/alterations

# Sub-endpoints (new hierarchical syntax)
jn cat @genomoncology/alterations/suggest -p gene=BRAF
jn cat @genomoncology/annotations/match --method POST < variants.txt
```

**Generation:**
```bash
# Selective: only generate what you specify
jn profile generate genomoncology \
  --from-openapi <url> \
  --endpoints "alterations,annotations,trials"

# Browse first, install later
jn profile browse genomoncology --from-openapi <url>
# Shows interactive list, pick with arrow keys

# Lazy: generate on first use
jn cat @genomoncology/alterations/suggest
# Prompts: "Endpoint not found. Generate from OpenAPI? [Y/n]"
```

---

## Core Ideas (Essential)

### 1. **Auto-Generate Profiles from OpenAPI**

**Problem:** Writing profiles manually is tedious and error-prone.

**Solution:**
```bash
jn profile generate genomoncology --from-openapi <url>
```

**What it does:**
- Extracts base URL, auth, timeout from spec
- Creates one source file per endpoint (or selectively)
- Maps OpenAPI parameters → JN params
- Includes descriptions from spec

**Benefits:**
- **Agents:** Discover and integrate APIs autonomously
- **Humans:** Zero manual config

---

### 2. **Parameter Validation**

**Problem:** Users pass unsupported parameters that APIs silently ignore (like we saw with `mutation_type_group`).

**Solution:** Validate parameters against OpenAPI schema before making API call.

**What it does:**
```bash
jn cat @genomoncology/alterations -p mutation_type_group=Insertion

# Warning: Parameter 'mutation_type_group' not supported
# Supported: gene, mutation_type, biomarker, page, limit
```

**Already implemented** in our recent fix! Just needs OpenAPI schemas.

**Benefits:**
- **Agents:** Fast fail without wasting API calls
- **Humans:** Immediate feedback on typos

---

### 3. **Inline Parameter Help**

**Problem:** Users don't know what parameters are available or what they mean.

**Solution:** Show parameter docs from OpenAPI in `--help`.

```bash
jn cat @genomoncology/alterations --help

Parameters (from OpenAPI spec):
  -p gene=VALUE          Gene symbol (required)
  -p mutation_type=VALUE Full mutation type (e.g., "Insertion - In frame")
  -p biomarker=VALUE     Biomarker filter (optional)
  -p limit=INTEGER       Results per page (default: 100, max: 1000)
  -p page=INTEGER        Page number (default: 1)
```

**Benefits:**
- **Agents:** Understand parameters programmatically
- **Humans:** Self-documenting commands

---

### 4. **Type Coercion & Defaults**

**Problem:** All CLI parameters are strings, but APIs expect typed values.

**Solution:** Use OpenAPI schemas to coerce types and apply defaults.

```bash
# User passes strings
jn cat @genomoncology/alterations -p limit=5 -p active=true

# JN coerces to correct types from OpenAPI schema:
# limit: 5 (integer)
# active: true (boolean)

# And applies defaults for missing params:
# page: 1 (default from spec)
```

**Benefits:**
- **Agents:** No manual type conversion
- **Humans:** Natural CLI experience

---

### 5. **Enum Validation & Suggestions**

**Problem:** Parameters with limited valid values (enums) cause errors.

**Solution:** Validate against enums, suggest corrections.

```bash
jn cat @genomoncology/trials -p status=recruiting

# Warning: Invalid value 'recruiting' for parameter 'status'
# Valid values: Recruiting, Active, Completed, Suspended
# Did you mean: Recruiting?
```

**Benefits:**
- **Agents:** Auto-correct case sensitivity
- **Humans:** No docs lookup needed

---

### 6. **Schema Diff for Migration**

**Problem:** APIs change, breaking existing workflows.

**Solution:** Diff OpenAPI specs to detect changes.

```bash
jn profile diff genomoncology --from v1.0.0 --to v1.1.0

Breaking changes:
  ~ /alterations: Parameter 'gene' now required (was optional)
  - /alterations_old: Deprecated (removal: 2026-01-01)

New features:
  + /therapies: New endpoint
  + /alterations: New parameter 'mutation_type_group'
```

**Benefits:**
- **Agents:** Detect breaking changes automatically
- **Humans:** Plan migrations strategically

---

## Reverse Engineering (Non-OpenAPI APIs)

Many APIs lack OpenAPI specs. How to generate profiles?

### Approach 1: Schema Inference from Examples

```bash
# Collect sample responses
jn cat https://api.example.com/users > samples.jsonl

# Infer JSON schema using GenSON library
jn profile infer genomoncology/alterations \
  --from-samples samples.jsonl \
  --base-url https://api.example.com

# Creates pseudo-OpenAPI spec from inferred schemas
```

**Library:** [GenSON](https://github.com/wolverdude/GenSON) - Infers JSON schemas from examples.

```python
from genson import SchemaBuilder
builder = SchemaBuilder()
builder.add_object({"gene": "BRAF", "id": 123})
builder.add_object({"gene": "EGFR", "id": 456})
schema = builder.to_schema()
# {"type": "object", "properties": {"gene": {"type": "string"}, "id": {"type": "integer"}}}
```

### Approach 2: LLM-Powered Documentation Scraping

```bash
# Point at API docs HTML
jn profile scrape genomoncology \
  --docs-url https://api.genomoncology.io/docs \
  --llm claude-3.5-sonnet

# LLM extracts:
# - Endpoint paths
# - Parameter descriptions
# - Example requests/responses
# - Generates pseudo-OpenAPI spec
```

**When to use:**
- Well-documented APIs without OpenAPI specs
- Interactive API explorers (Swagger UI without downloadable spec)

### Approach 3: Interactive Exploration

```bash
jn profile learn genomoncology

> Base URL: https://api.genomoncology.io
> Endpoint path: /alterations
> Method: GET
> Try it? [Y/n] y
> [Makes request, shows response]
> Parameters found: gene, mutation_type (inferred from response)
> Save this endpoint? [Y/n] y
```

**When to use:**
- Undocumented APIs
- Learning by experimentation

---

## Scale Considerations

### The Real Problem

GenomOncology has **227 endpoints**. If we auto-generated everything:

```bash
genomoncology/
├── alterations.json
├── alterations_actionability.json
├── alterations_biomarker_bridge.json
├── alterations_canonical_alterations_suggest.json
├── alterations_case_alterations_suggest.json
... (222 more files) ❌
```

This would be:
- **Overwhelming** to navigate
- **Wasteful** (we only use 2.6% of endpoints)
- **Confusing** (unclear naming like `alterations_canonical_alterations_suggest.json`)

### Solutions

**1. Selective Generation (Recommended)**

Only generate what you specify:
```bash
jn profile generate genomoncology \
  --from-openapi <url> \
  --endpoints "alterations,annotations,trials"

# Creates only:
# - alterations.json
# - annotations.json
# - trials.json (not clinical_trials!)
```

**2. Hierarchical Sub-Endpoints**

Main endpoints are files, sub-endpoints are directories:
```bash
genomoncology/
├── alterations.json              # Main
├── alterations/
│   ├── suggest.json              # Sub-endpoint
│   └── validate.json
├── annotations.json              # Main
└── annotations/
    └── match.json                # Sub-endpoint
```

Usage:
```bash
jn cat @genomoncology/alterations              # Main
jn cat @genomoncology/alterations/suggest      # Sub
```

**3. Lazy Loading**

Generate on first use:
```bash
jn cat @genomoncology/alterations/suggest

# First time: Prompts "Endpoint not found. Generate from OpenAPI? [Y/n]"
# Generates: genomoncology/alterations/suggest.json
# Subsequent uses: Just works
```

**4. Interactive Browse**

Explore before committing:
```bash
jn profile browse genomoncology --from-openapi <url>

# Shows:
# ┌─ GenomOncology API (227 endpoints) ─┐
# │ [✓] alterations        (9 endpoints)│
# │ [ ] annotations       (20 endpoints)│
# │ [ ] users             (27 endpoints)│
# │ [✓] trials            (17 endpoints)│
# └─────────────────────────────────────┘
#
# Arrow keys to navigate, Space to select, Enter to generate
```

### Recommendation

For huge APIs:
1. **Start minimal** - Generate only core endpoints (alterations, annotations)
2. **Add on-demand** - Use lazy loading for rare endpoints
3. **Group logically** - Use hierarchical structure for related endpoints

---

## Implementation Priority

### Phase 1 (MVP)
1. Auto-generate profiles from OpenAPI
2. Parameter validation (extend existing validation)
3. Inline parameter help

### Phase 2 (Enhanced)
4. Type coercion & defaults
5. Enum validation
6. Reverse engineering tools (GenSON + LLM scraper)

### Phase 3 (Advanced)
7. Schema diff for migrations
8. Auto-complete parameter names
9. Cost/rate limit discovery

---

## Benefits Summary

### For Agents
- **Autonomous integration** - Discover APIs without humans
- **Fast failure** - Validate before API calls
- **Adaptation** - Detect breaking changes
- **Self-documentation** - Learn APIs from specs

### For Humans
- **Zero config** - Auto-generate profiles
- **Inline help** - Docs in terminal
- **Immediate feedback** - Validate parameters
- **Migration planning** - Diff specs

---

## Open Questions

**Q: Should we generate all endpoints or just popular ones?**
- Start selective (user picks endpoints)
- Add lazy loading later
- Avoid overwhelming users

**Q: How to handle versioned APIs?**
```bash
jn cat @api:v1/users  # Use v1
jn cat @api:v2/users  # Use v2
```

**Q: Store profiles as multiple files or single file?**
- Multiple files: better for git, modular, but clutters filesystem
- Single file: cleaner, but harder to manage large APIs
- **Recommendation:** Multiple files, but selective generation

---

## Related Documents

- `rest-api-profiles.md` - Current profile system
- `genomoncology-api.md` - Real-world example
- `roadmap.md` - Implementation timeline
