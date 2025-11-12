# OpenAPI/Swagger Integration for JN

## The Problem

APIs with OpenAPI specs contain rich metadata (parameters, types, descriptions, examples) that could enhance JN profiles. But huge APIs (100+ endpoints) could generate overwhelming profile directories.

**Reality Check:**
```bash
# GenomOncology might have 50+ endpoints
jn profile generate genomoncology --from-openapi

# Creates 50+ files in ~/.local/jn/profiles/http/genomoncology/
# Overwhelming? Maybe. Useful? Depends.
```

## Solution: Selective Generation

Don't generate everything - let users pick what they need:

```bash
# Generate specific endpoints only
jn profile generate genomoncology \
  --from-openapi https://api.genomoncology.io/schema \
  --endpoints "alterations,annotations,clinical_trials"

# Or generate all, but store in single file for browsing
jn profile generate genomoncology \
  --from-openapi https://api.genomoncology.io/schema \
  --preview > genomoncology-all-endpoints.json

# Then cherry-pick endpoints to actually install
jn profile install genomoncology/alterations
jn profile install genomoncology/annotations
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

### Problem: Huge APIs

Some APIs have 100+ endpoints. Generating profiles for all creates clutter.

### Solutions:

**1. Selective Generation**
```bash
# Only generate what you need
jn profile generate api --endpoints "users,posts,comments"
```

**2. Lazy Loading**
```bash
# Generate on-demand when first used
jn cat @api/rare-endpoint
# Prompts: "Profile not found. Generate from OpenAPI spec? [Y/n]"
```

**3. Preview Before Install**
```bash
# Browse all endpoints without installing
jn profile browse api --from-openapi <url>
# Interactive picker: arrow keys to select, space to mark, enter to install
```

**4. Hierarchical Grouping**
```
genomoncology/
├── _meta.json (5 lines)
├── core/        # Frequently used
│   ├── alterations.json
│   └── annotations.json
└── admin/       # Rarely used
    ├── users.json
    └── audit_logs.json
```

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
