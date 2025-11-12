# OpenAPI/Swagger Integration - 20 Ideas for JN Enhancement

## Overview

OpenAPI/Swagger specifications provide machine-readable API documentation that can dramatically improve JN's HTTP profile system. This document explores 20 ways OpenAPI specs could enhance both agent and human workflows.

## Context

**OpenAPI Structure:**
```yaml
openapi: 3.0.0
info:
  title: GenomOncology API
  version: 1.0.0
servers:
  - url: https://api.genomoncology.io
paths:
  /alterations:
    get:
      operationId: listAlterations
      summary: List genetic alterations
      parameters:
        - name: gene
          in: query
          schema:
            type: string
      responses:
        200:
          content:
            application/json:
              schema:
                type: object
                properties:
                  results:
                    type: array
```

---

## 20 Ideas for OpenAPI Integration

### 1. **Automatic Profile Generation**

**What:** Generate complete JN profiles from OpenAPI specs with a single command.

**How:**
```bash
jn profile generate genomoncology --from-openapi https://pwb-demo.genomoncology.io/api/schema

# Creates:
# ~/.local/jn/profiles/http/genomoncology/_meta.json
# ~/.local/jn/profiles/http/genomoncology/alterations.json
# ~/.local/jn/profiles/http/genomoncology/annotations.json
# ... (one file per endpoint)
```

**Benefits for Agents:**
- Agents can discover and integrate new APIs without human intervention
- Automatically stays in sync with API changes

**Benefits for Humans:**
- Zero-config setup for any OpenAPI-compliant API
- No manual JSON writing required

**Implementation:**
```python
def generate_profile_from_openapi(spec_url):
    spec = requests.get(spec_url).json()

    # Create _meta.json from spec.servers and spec.security
    meta = {
        "base_url": spec["servers"][0]["url"],
        "headers": extract_auth_headers(spec["security"])
    }

    # Create one source file per path
    for path, methods in spec["paths"].items():
        source_name = extract_source_name(path)
        source_config = {
            "path": path,
            "method": list(methods.keys())[0].upper(),
            "params": extract_parameters(methods),
            "description": methods.get("summary", "")
        }
```

---

### 2. **Parameter Validation with Schemas**

**What:** Validate query parameters before making API calls using OpenAPI schemas.

**Example:**
```yaml
# OpenAPI spec
parameters:
  - name: gene
    in: query
    required: true
    schema:
      type: string
      pattern: "^[A-Z0-9]+$"
  - name: limit
    in: query
    schema:
      type: integer
      minimum: 1
      maximum: 1000
```

**JN Usage:**
```bash
# Valid
jn cat @genomoncology/alterations -p gene=EGFR -p limit=5

# Invalid - warns before API call
jn cat @genomoncology/alterations -p gene=egfr -p limit=99999
# Warning: Parameter 'gene' must match pattern ^[A-Z0-9]+$
# Warning: Parameter 'limit' exceeds maximum 1000
```

**Benefits for Agents:**
- Fast fail before expensive API calls
- Self-correct parameters based on schema constraints

**Benefits for Humans:**
- Immediate feedback on typos/mistakes
- Learn API constraints without reading docs

---

### 3. **Auto-Complete Parameter Names**

**What:** Shell completion for parameter names from OpenAPI specs.

**Example:**
```bash
jn cat @genomoncology/alterations -p <TAB>
# Shows: gene, mutation_type, biomarker, page, limit

jn cat @genomoncology/alterations -p gene=EGFR -p <TAB>
# Shows remaining params: mutation_type, biomarker, page, limit
```

**Benefits for Agents:**
- Discover available parameters programmatically
- Build correct requests without hardcoding parameter names

**Benefits for Humans:**
- Faster command composition
- Discoverability without leaving terminal

**Implementation:**
- Generate bash/zsh completion scripts from OpenAPI specs
- Update completions when profiles are regenerated

---

### 4. **Inline Parameter Documentation**

**What:** Show parameter descriptions and examples from OpenAPI in help text.

**Example:**
```bash
jn cat @genomoncology/alterations --help

Parameters (from OpenAPI spec):
  -p gene=VALUE          Gene symbol (e.g., BRAF, EGFR, KRAS)
  -p mutation_type=VALUE Mutation type (e.g., "Substitution - Missense")
                         Valid values: see /api/mutation_types
  -p biomarker=VALUE     Biomarker filter
  -p limit=INTEGER       Results per page (default: 100, max: 1000)
  -p page=INTEGER        Page number (default: 1)
```

**Benefits for Agents:**
- Understand parameter semantics without external docs
- Generate example queries from OpenAPI examples

**Benefits for Humans:**
- Self-documenting commands
- No need to switch to browser for API docs

---

### 5. **Response Schema Validation**

**What:** Validate API responses against OpenAPI schemas to detect breaking changes.

**Example:**
```bash
jn cat @genomoncology/alterations --validate-response | head -5

# If response doesn't match schema:
# Warning: Response validation failed
# - Missing required field: 'pagination'
# - Field 'results' expected array, got object
# - Extra field 'new_field' not in schema (may indicate API update)
```

**Benefits for Agents:**
- Detect API changes immediately
- Gracefully handle schema evolution

**Benefits for Humans:**
- Early warning of API breaking changes
- Confidence that data format is correct

---

### 6. **Automatic Error Code Documentation**

**What:** Display error meanings from OpenAPI response definitions.

**Example:**
```bash
jn cat @genomoncology/alterations -p gene=INVALID_GENE

Error 400: Bad Request
From OpenAPI spec:
  "Invalid gene symbol. Use /genes endpoint to list valid symbols."

Suggested fix:
  jn cat @genomoncology/genes | jq -r '.[] | .symbol' | grep INVALID
```

**Benefits for Agents:**
- Understand error semantics programmatically
- Implement retry logic based on error types

**Benefits for Humans:**
- Clear error messages with actionable suggestions
- No need to search documentation for error codes

---

### 7. **Discover Related Endpoints**

**What:** Show related endpoints based on OpenAPI tags and relationships.

**Example:**
```bash
jn profile endpoints genomoncology/alterations --related

Related endpoints for /alterations:
  @genomoncology/alterations/{id}  - Get alteration detail
  @genomoncology/annotations       - Get variant annotations
  @genomoncology/clinical_trials   - Find trials by alteration

Common workflow:
  jn cat @genomoncology/alterations -p gene=BRAF | \
    jn filter '.results[0] | .id' | \
    xargs -I {} jn cat @genomoncology/alterations/{}
```

**Benefits for Agents:**
- Discover multi-step workflows automatically
- Build complex pipelines from API relationships

**Benefits for Humans:**
- Learn API structure without reading docs
- Find relevant endpoints quickly

---

### 8. **Generate Example Queries**

**What:** Create runnable examples from OpenAPI example values.

**Example:**
```bash
jn profile examples genomoncology/alterations

Example 1: List BRAF alterations
  jn cat @genomoncology/alterations -p gene=BRAF

Example 2: Filter missense mutations
  jn cat @genomoncology/alterations -p gene=EGFR -p mutation_type="Substitution - Missense"

Example 3: Paginate results
  jn cat @genomoncology/alterations -p gene=KRAS -p limit=10 -p page=2
```

**Benefits for Agents:**
- Generate test queries automatically
- Learn API usage patterns from examples

**Benefits for Humans:**
- Quick start without reading full docs
- Copy-paste working examples

---

### 9. **Enum Value Validation**

**What:** Validate parameter values against OpenAPI enums.

**Example:**
```yaml
# OpenAPI
parameters:
  - name: status
    schema:
      type: string
      enum: [Recruiting, Active, Completed, Suspended]
```

**JN Usage:**
```bash
jn cat @genomoncology/clinical_trials -p status=recruiting

Warning: Parameter 'status' has invalid value 'recruiting'
Valid values: Recruiting, Active, Completed, Suspended
Did you mean: Recruiting?
```

**Benefits for Agents:**
- Auto-correct common mistakes (case sensitivity)
- Discover valid options programmatically

**Benefits for Humans:**
- Immediate feedback on typos
- Learn enum values without docs

---

### 10. **Dependency Detection**

**What:** Identify required vs optional parameters from OpenAPI.

**Example:**
```bash
jn cat @genomoncology/annotations

Error: Missing required parameters
From OpenAPI spec:
  Required: At least one of [hgvs_g, hgvs_c, gene]
  Provided: none

Example:
  jn cat @genomoncology/annotations -p hgvs_g="chr7:g.140453136A>T"
```

**Benefits for Agents:**
- Construct valid requests without trial-and-error
- Understand parameter dependencies

**Benefits for Humans:**
- Clear error messages about what's missing
- No API calls wasted on invalid requests

---

### 11. **Rate Limit Discovery**

**What:** Extract rate limits from OpenAPI `x-rateLimit-*` extensions.

**Example:**
```yaml
# OpenAPI
paths:
  /alterations:
    get:
      x-rateLimit-limit: 1000
      x-rateLimit-period: 3600
```

**JN Usage:**
```bash
jn cat @genomoncology/alterations

# Shows in verbose mode:
Rate limit: 1000 requests per hour
Current usage: 247/1000 (from X-RateLimit-Remaining header)
Resets at: 2025-11-12 02:30:00 UTC
```

**Benefits for Agents:**
- Implement backoff automatically
- Schedule requests to stay under limits

**Benefits for Humans:**
- Understand API constraints upfront
- Plan batch operations accordingly

---

### 12. **Authentication Flow Documentation**

**What:** Generate auth setup instructions from OpenAPI security schemes.

**Example:**
```bash
jn profile auth-setup genomoncology

Authentication required: apiKey in header
Setup instructions:
  1. Get API key from: https://pwb-demo.genomoncology.io/api-keys
  2. Set environment variable:
       export GENOMONCOLOGY_API_KEY="your-token-here"
  3. Test connection:
       jn cat @genomoncology/alterations -p limit=1

Security scheme (from OpenAPI):
  Type: apiKey
  Name: Authorization
  Format: Token {key}
```

**Benefits for Agents:**
- Understand auth requirements without human intervention
- Generate credential setup instructions

**Benefits for Humans:**
- Step-by-step setup guide
- Know exactly which env vars to set

---

### 13. **Versioned Profile Generation**

**What:** Generate profiles for multiple API versions from OpenAPI.

**Example:**
```bash
jn profile generate genomoncology --from-openapi https://api.genomoncology.io/api/schema --version v1
jn profile generate genomoncology --from-openapi https://api.genomoncology.io/v2/schema --version v2

# Usage:
jn cat @genomoncology:v1/alterations  # Uses v1 API
jn cat @genomoncology:v2/alterations  # Uses v2 API
```

**Benefits for Agents:**
- Support multiple API versions simultaneously
- Test migrations between versions

**Benefits for Humans:**
- Gradual migration to new API versions
- Compare behavior across versions

---

### 14. **Request/Response Examples as Tests**

**What:** Generate test cases from OpenAPI request/response examples.

**Example:**
```bash
jn profile generate-tests genomoncology --from-openapi-examples

# Creates:
# tests/profiles/test_genomoncology.py
#
# def test_alterations_list():
#     result = run(["cat", "@genomoncology/alterations", "-p", "gene=BRAF"])
#     assert "results" in result
#     assert result["results"][0]["gene"] == "BRAF"
```

**Benefits for Agents:**
- Validate profile correctness automatically
- Detect API changes via test failures

**Benefits for Humans:**
- Confidence that profiles work
- Regression testing for API updates

---

### 15. **Pagination Pattern Detection**

**What:** Auto-detect pagination from OpenAPI and provide helpers.

**Example:**
```yaml
# OpenAPI
parameters:
  - name: page
    in: query
    schema:
      type: integer
  - name: limit
    in: query
responses:
  200:
    headers:
      X-Total-Count:
        schema:
          type: integer
```

**JN Usage:**
```bash
# Auto-paginate all results
jn cat @genomoncology/alterations -p gene=EGFR --auto-paginate

# Or explicit page range
jn cat @genomoncology/alterations -p gene=EGFR --pages 1-10
```

**Benefits for Agents:**
- Fetch all data without manual pagination logic
- Respect rate limits while paginating

**Benefits for Humans:**
- No need to write pagination loops
- Get complete datasets easily

---

### 16. **Content Type Negotiation**

**What:** Support multiple response formats from OpenAPI.

**Example:**
```yaml
# OpenAPI
responses:
  200:
    content:
      application/json: {...}
      text/csv: {...}
      application/xml: {...}
```

**JN Usage:**
```bash
# Default: JSON → NDJSON
jn cat @genomoncology/alterations

# Request CSV directly
jn cat @genomoncology/alterations --accept text/csv

# Request XML (converted to NDJSON)
jn cat @genomoncology/alterations --accept application/xml
```

**Benefits for Agents:**
- Optimize data transfer format
- Handle APIs with multiple formats

**Benefits for Humans:**
- Get data in preferred format
- Avoid unnecessary conversions

---

### 17. **Webhook/Callback Discovery**

**What:** Document async endpoints from OpenAPI webhooks.

**Example:**
```yaml
# OpenAPI
webhooks:
  annotationComplete:
    post:
      requestBody:
        content:
          application/json:
            schema:
              properties:
                status: {type: string}
                results: {type: object}
```

**JN Usage:**
```bash
jn profile webhooks genomoncology

Available webhooks:
  annotationComplete - Fired when batch annotation completes
    Method: POST
    Payload: {status, results}

Setup:
  jn webhook listen genomoncology/annotationComplete --port 8080
```

**Benefits for Agents:**
- Handle async operations properly
- Set up webhook listeners automatically

**Benefits for Humans:**
- Understand async API patterns
- Test webhooks locally

---

### 18. **Deprecation Warnings**

**What:** Detect deprecated endpoints from OpenAPI metadata.

**Example:**
```yaml
# OpenAPI
paths:
  /alterations_old:
    deprecated: true
    get:
      summary: "DEPRECATED: Use /alterations instead"
```

**JN Usage:**
```bash
jn cat @genomoncology/alterations_old

Warning: This endpoint is deprecated (from OpenAPI spec)
  Reason: Use /alterations instead
  Removal: Version 2.0 (2026-01-01)

Suggested alternative:
  jn cat @genomoncology/alterations
```

**Benefits for Agents:**
- Migrate to new endpoints proactively
- Track API evolution

**Benefits for Humans:**
- Early warning of upcoming changes
- Clear migration path

---

### 19. **Cost Estimation (if available)**

**What:** Show API call costs from OpenAPI `x-pricing` extensions.

**Example:**
```yaml
# OpenAPI
paths:
  /annotations:
    post:
      x-pricing:
        cost: 0.01
        unit: request
        currency: USD
```

**JN Usage:**
```bash
jn cat @genomoncology/annotations --estimate-cost

Estimated cost for this query:
  Requests: ~100 (pagination)
  Cost per request: $0.01 USD
  Total: $1.00 USD

Proceed? [y/N]
```

**Benefits for Agents:**
- Budget-aware API usage
- Optimize queries to minimize cost

**Benefits for Humans:**
- Understand cost implications upfront
- Avoid expensive operations by mistake

---

### 20. **Diff Between Schema Versions**

**What:** Compare OpenAPI specs to detect API changes.

**Example:**
```bash
jn profile diff genomoncology --old v1.0.0 --new v1.1.0

Changes in v1.1.0:
  New endpoints:
    + /therapies
    + /diseases

  Modified endpoints:
    ~ /alterations
      + New parameter: 'mutation_type_group' (string, optional)
      ~ Parameter 'gene' now required (was optional)
      - Removed deprecated parameter 'legacy_id'

  Deprecated endpoints:
    ! /alterations_old (removal: 2026-01-01)

  Breaking changes: 1
  New features: 3
  Deprecations: 1
```

**Benefits for Agents:**
- Detect breaking changes automatically
- Prioritize migration tasks

**Benefits for Humans:**
- Understand what changed between versions
- Plan migrations strategically

---

## Reverse Engineering OpenAPI for Non-Spec APIs

### Can we create pseudo-OpenAPI specs for APIs without official schemas?

**Yes! Several approaches:**

### Approach 1: Traffic Inspection + LLM

```bash
# Capture API traffic
jn cat https://api.example.com/users > sample_users.json
jn cat https://api.example.com/posts > sample_posts.json

# Generate pseudo-OpenAPI spec using LLM
jn profile reverse-engineer example-api \
  --from-samples sample_*.json \
  --base-url https://api.example.com

# Uses LLM to:
# 1. Infer schemas from JSON samples (using genson/GenSON library)
# 2. Detect patterns (pagination, auth, etc)
# 3. Generate reasonable parameter names
# 4. Create OpenAPI-like spec
```

**Library:** [GenSON](https://github.com/wolverdude/GenSON) - Python library that infers JSON schemas from examples

**Example:**
```python
from genson import SchemaBuilder

builder = SchemaBuilder()
builder.add_object({"name": "Alice", "age": 30})
builder.add_object({"name": "Bob", "age": 25})

schema = builder.to_schema()
# {
#   "type": "object",
#   "properties": {
#     "name": {"type": "string"},
#     "age": {"type": "integer"}
#   }
# }
```

### Approach 2: HTTP Archive (HAR) Analysis

```bash
# Export HAR from browser DevTools
# File contains all API calls with headers, params, responses

jn profile generate-from-har example-api --har recorded_session.har

# Analyzes:
# - Request patterns (query params, headers)
# - Response structures
# - Authentication methods
# - Endpoints and methods
```

### Approach 3: Interactive API Exploration

```bash
# Start interactive profiler
jn profile learn example-api --base-url https://api.example.com

# Interactive prompts:
> Enter endpoint path: /users
> Parameters found in docs: id, limit, offset
> Test request? [Y/n] y
> [Makes request, shows response structure]
> Save this endpoint? [Y/n] y
> Inferred schema: {type: array, items: {type: object, properties: {...}}}
> Continue? [Y/n] y
```

### Approach 4: LLM-Powered Documentation Scraper

```bash
# Point to API documentation page
jn profile scrape-docs example-api \
  --docs-url https://example.com/api-docs \
  --llm-model claude-3.5-sonnet

# LLM reads HTML docs and extracts:
# - Endpoint descriptions
# - Parameter specifications
# - Example requests/responses
# - Authentication requirements
# - Generates pseudo-OpenAPI spec
```

**Libraries that could help:**
- **genson/GenSON** - JSON schema inference from examples
- **hypothesis** - Generate test data from schemas (property-based testing)
- **openapi-spec-validator** - Validate generated specs
- **Fuzz testing tools** - Discover parameter types by trying different inputs

---

## Benefits Summary

### For AI Agents:

1. **Self-service API integration** - Discover and use new APIs autonomously
2. **Fast failure** - Validate before expensive API calls
3. **Automatic adaptation** - Detect API changes and adjust
4. **Workflow discovery** - Find related endpoints and build pipelines
5. **Cost optimization** - Understand rate limits and pricing
6. **Error recovery** - Parse error semantics programmatically
7. **Schema learning** - Build mental models of API structure

### For Human Users:

1. **Zero-config setup** - Auto-generate profiles from OpenAPI
2. **Inline documentation** - Help text from API specs
3. **Immediate feedback** - Validate parameters before API calls
4. **Discoverability** - Tab completion and examples
5. **Cost transparency** - Understand pricing upfront
6. **Version management** - Work with multiple API versions
7. **Migration planning** - Diff specs to understand changes
8. **Self-documenting commands** - No need to leave terminal

---

## Implementation Priority

### Phase 1 (High Impact, Low Complexity):
1. Automatic profile generation (Idea #1)
2. Parameter validation (Idea #2)
3. Inline parameter documentation (Idea #4)
4. Generate example queries (Idea #8)

### Phase 2 (High Impact, Medium Complexity):
5. Auto-complete parameter names (Idea #3)
6. Automatic error code documentation (Idea #6)
7. Enum value validation (Idea #9)
8. Authentication flow documentation (Idea #12)

### Phase 3 (Medium Impact, High Complexity):
9. Response schema validation (Idea #5)
10. Discover related endpoints (Idea #7)
11. Pagination pattern detection (Idea #15)
12. Diff between schema versions (Idea #20)

### Phase 4 (Future Enhancements):
13-19. Advanced features (webhooks, cost estimation, etc.)

---

## Related Documents

- `rest-api-profiles.md` - Current profile system design
- `genomoncology-api.md` - Real-world profile example
- `roadmap.md` - Implementation timeline

## Next Steps

1. Fetch GenomOncology OpenAPI spec and analyze structure
2. Implement basic profile generator (Phase 1, Idea #1)
3. Add parameter validation using schemas (Phase 1, Idea #2)
4. Create reverse-engineering tool for non-OpenAPI APIs
