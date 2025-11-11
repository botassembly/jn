# API Parameter Patterns - Architectural Analysis

## Problem Statement

The GenomOncology profile documentation shows this syntax:
```bash
jn cat "@genomoncology/alterations?gene=BRAF"
```

This embeds HTTP query parameters in the profile reference using `?` syntax. Is this the right approach, or should we use JN's existing `-p/--param` pattern?

## Current JN Parameter Patterns

### 1. Plugin-Level Options (Parsed by Plugin)

**Example:**
```bash
jn put --plugin table --tablefmt grid output.csv
```

**How it works:**
- CLI passes `--tablefmt grid` to plugin as argv
- Plugin's `__main__` parses arguments using argparse
- Plugin builds config dict and calls `writes(config)`

**Code:** `jn_home/plugins/formats/table_.py:355`

**Pattern:**
- Command → Plugin (direct passthrough of options)
- Plugin owns parsing logic
- Plugin-specific options (table format, CSV delimiter, etc.)

---

### 2. Profile Parameters (Parsed by Framework)

**Example:**
```bash
jn filter '@analytics/pivot' -p row=product -p col=month
```

**How it works:**
- Framework resolves profile path: `profiles/jq/analytics/pivot.jq`
- Framework reads file content
- Framework substitutes `$row` → `"product"`, `$col` → `"month"`
- Framework passes resolved query to plugin

**Code:** `src/jn/profiles/resolver.py:27`

**Pattern:**
- Command → Framework (resolves + substitutes) → Plugin (receives final content)
- Framework owns parameter substitution
- Generic parameters (any key=value pair)

---

### 3. Command-Level Options (Parsed by Click)

**Example:**
```bash
jn put --plugin table output.csv
```

**How it works:**
- Click parses `--plugin table` before calling function
- Command function receives parsed args
- Command passes config to pipeline functions

**Code:** `src/jn/cli/commands/put.py:12`

**Pattern:**
- CLI (Click) → Command → Pipeline
- Command owns orchestration
- Command-specific options (input/output selection, etc.)

---

## The Question Mark Dilemma

### Option 1: Query String in URL (Current Docs)

**Syntax:**
```bash
jn cat "@genomoncology/alterations?gene=BRAF&mutation_type=Missense"
```

**Pros:**
- ✅ Follows HTTP conventions (familiar to API users)
- ✅ Visually clear: "this is a URL with query params"
- ✅ Compact syntax
- ✅ Natural for HTTP-specific use case
- ✅ Mirrors curl/browser behavior

**Cons:**
- ❌ Invents new syntax in JN (inconsistent with -p pattern)
- ❌ Requires shell quoting (`"@genomoncology/..."`)
- ❌ Parsing complexity (split on ? before profile resolution)
- ❌ Only makes sense for HTTP profiles (not generic)
- ❌ Doesn't leverage existing -p infrastructure

**Implementation:**
```python
# In resolve_profile_reference():
if "?" in reference:
    reference, query_string = reference.split("?", 1)
    # ... resolve profile ...
    url = f"{url}?{query_string}"
```

**Who does it this way?**
- `curl` - `curl "https://api.com/endpoint?param=value"`
- Web browsers - `https://example.com/search?q=term`
- HTTP clients - `requests.get(url, params={'key': 'value'})`

---

### Option 2: Use Existing -p Pattern (Framework-Managed)

**Syntax:**
```bash
jn cat @genomoncology/alterations -p gene=BRAF -p mutation_type=Missense
```

**Pros:**
- ✅ Consistent with existing JN filter params
- ✅ No new syntax to learn
- ✅ No shell quoting needed
- ✅ Reuses existing parameter infrastructure
- ✅ Works for any profile (not HTTP-specific)
- ✅ Clear separation: profile reference vs parameters

**Cons:**
- ❌ `cat` command doesn't currently accept -p
- ❌ More verbose than query string
- ❌ Less obvious it's for HTTP (not domain-specific)
- ❌ Requires framework to understand HTTP query params
- ❌ Parameter substitution happens in profile content (not URL construction)

**Implementation:**
```python
# src/jn/cli/commands/cat.py
@click.option("--param", "-p", multiple=True)
def cat(ctx, input_file, param):
    # Parse params
    params = {k: v for p in param for k, v in [p.split("=", 1)]}
    # Pass to read_source()
```

**Who does it this way?**
- `ffmpeg` - `ffmpeg -i input.mp4 -vcodec h264 -acodec aac`
- `docker run` - `docker run -e KEY=value -e FOO=bar`
- `kubectl` - `kubectl get pods -l app=myapp -l env=prod`

---

### Option 3: Hybrid Approach (Best of Both)

**Syntax:**
```bash
# For simple params (managed by framework):
jn cat @genomoncology/alterations -p gene=BRAF

# For raw HTTP query strings (pass-through):
jn cat "@genomoncology/alterations?limit=100&page=2"

# Combined (params + raw):
jn cat "@genomoncology/alterations?limit=100" -p gene=BRAF
# → https://api.com/alterations?limit=100&gene=BRAF
```

**Pros:**
- ✅ Flexible: supports both patterns
- ✅ Params for structured data (-p)
- ✅ Query string for HTTP-specific features (pagination, ?limit, ?format)
- ✅ Clear semantics: -p for profile params, ? for HTTP pass-through

**Cons:**
- ❌ Two ways to do the same thing (confusing)
- ❌ Complexity: when to use -p vs ?
- ❌ Still requires shell quoting for ?

**Implementation:**
```python
# Support both:
# 1. Parse -p params and add to query string
# 2. Parse ? query string and merge
# 3. Combine into final URL
```

**Who does it this way?**
- `aws s3` - `aws s3 cp file.txt s3://bucket/key --metadata key=value`
  (flags for CLI params, path for S3 resources)

---

### Option 4: Config File / JSON Inline

**Syntax:**
```bash
# JSON inline:
jn cat @genomoncology/alterations --params '{"gene":"BRAF","mutation_type":"Missense"}'

# Config file:
echo '{"gene":"BRAF"}' | jn cat @genomoncology/alterations --params-stdin
```

**Pros:**
- ✅ Supports complex params (arrays, nested objects)
- ✅ No shell escaping issues
- ✅ Reusable config files

**Cons:**
- ❌ Very verbose for simple cases
- ❌ Requires JSON knowledge
- ❌ Not intuitive for quick queries

---

### Option 5: Named Sources (Profile-Managed)

**Syntax:**
```bash
# Profile defines sources with params:
# alterations_by_gene.json:
{
  "path": "/alterations",
  "params": {
    "gene": "${gene}",
    "mutation_type": "${mutation_type}"
  }
}

# Usage:
jn cat @genomoncology/alterations_by_gene -p gene=BRAF
```

**Pros:**
- ✅ Encapsulates API-specific param logic in profile
- ✅ Type-safe (profile knows valid params)
- ✅ Reusable configurations
- ✅ Uses existing -p pattern

**Cons:**
- ❌ Requires profile per param combination
- ❌ Less flexible for ad-hoc queries
- ❌ More files to manage

---

## Architectural Analysis

### Core Question: Is Query String Generic or HTTP-Specific?

**Query strings are fundamentally HTTP-specific:**
- Syntax: `?key=value&key2=value2`
- Encoding: URL encoding (`%20` for spaces, etc.)
- Semantics: HTTP GET request parameters
- Not applicable to: CSV files, JSON files, databases, etc.

**JN's -p pattern is generic:**
- Works for any plugin (jq, http, sql, etc.)
- Framework-agnostic substitution
- Key-value pairs without protocol assumptions

**Conclusion:** Query strings belong in the HTTP layer, not the generic framework.

---

### Where Should HTTP Query Params Be Handled?

**Three layers in JN:**

1. **Framework Layer (cat, filter, put)**
   - Generic commands that work with any plugin
   - Should not know about HTTP-specific syntax

2. **Profile Layer (@api/source)**
   - Configuration for specific APIs
   - Could encode HTTP-specific rules

3. **Plugin Layer (http_.py)**
   - HTTP-specific implementation
   - Natural place for query string handling

**Analysis:**

| Layer | Query String? | Reasoning |
|-------|--------------|-----------|
| Framework | ❌ No | Breaking generic abstraction |
| Profile | ⚠️ Maybe | Profiles are API-specific config |
| Plugin | ✅ Yes | Plugin knows HTTP protocol |

**Best practice:** Keep HTTP details in HTTP plugin/profile layer, not framework.

---

### Comparison with Other CLI Tools

**curl (HTTP-native):**
```bash
curl "https://api.com/endpoint?param=value"
```
- Makes sense: curl IS an HTTP tool
- Query strings are first-class

**aws (Service-native):**
```bash
aws s3 ls s3://bucket/prefix --page-size 100
```
- Uses flags (--page-size) for structured params
- Service-specific but consistent with CLI patterns

**kubectl (Resource-native):**
```bash
kubectl get pods -l key=value
```
- Uses flags (-l) for selectors
- Consistent with Unix flag conventions

**JN (Protocol-agnostic):**
- Should follow Unix/CLI conventions (-p flags)
- Not HTTP-native (works with CSV, JSON, SQL, etc.)
- Query strings break abstraction

---

## Recommendation: Option 2 with Framework Enhancement

### Proposed Solution

**Use -p pattern for all profile parameters, including HTTP:**

```bash
# Instead of:
jn cat "@genomoncology/alterations?gene=BRAF"

# Use:
jn cat @genomoncology/alterations -p gene=BRAF -p mutation_type=Missense
```

**Why this is better:**

1. **Consistency:** Matches `jn filter '@profile' -p key=value`
2. **Generic:** Works for any profile type (not just HTTP)
3. **No New Syntax:** Leverage existing -p infrastructure
4. **Extensible:** Can support complex params later (`-p "filter={\"age\": {\"$gt\": 25}}"`)
5. **Shell-Friendly:** No quoting required for simple cases

---

### Implementation Plan

**Step 1: Add -p to cat command**

```python
# src/jn/cli/commands/cat.py
@click.command()
@click.argument("input_file")
@click.option("--param", "-p", multiple=True, help="Profile parameter (key=value)")
@pass_context
def cat(ctx, input_file, param):
    """Read file and output NDJSON to stdout."""
    params = {}
    for p in param:
        if "=" not in p:
            raise ValueError(f"Invalid param: {p}")
        key, value = p.split("=", 1)
        params[key] = value

    read_source(input_file, ctx.plugin_dir, ctx.cache_path,
                output_stream=sys.stdout, params=params)
```

**Step 2: HTTP profile resolver handles params**

```python
# src/jn/profiles/http.py
def resolve_profile_reference(reference: str, params: dict = None) -> Tuple[str, dict]:
    """Resolve @api/source reference to URL and headers.

    Args:
        reference: Profile reference like "@genomoncology/alterations"
        params: Optional query parameters like {"gene": "BRAF"}

    Returns:
        Tuple of (url, headers_dict)
    """
    # Load profile
    profile = load_hierarchical_profile(api_name, source_name)

    # Build base URL
    base_url = substitute_env_vars(profile.get("base_url", ""))
    path = profile.get("path", "")
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    # Add query params if provided
    if params:
        from urllib.parse import urlencode
        query_string = urlencode(params)
        url = f"{url}?{query_string}"

    # Build headers
    headers = profile.get("headers", {})
    resolved_headers = {k: substitute_env_vars(v) for k, v in headers.items()}

    return url, resolved_headers
```

**Step 3: Update pipeline to pass params**

```python
# src/jn/core/pipeline.py
def read_source(source: str, ..., params: dict = None):
    """Read a source file or URL."""
    if source.startswith("@"):
        url, headers = resolve_profile_reference(source, params)
        # ... rest
```

---

### Migration Path

**Current docs show:**
```bash
jn cat "@genomoncology/alterations?gene=BRAF"
```

**Step 1: Support both syntaxes (backward compat)**
```python
# Parse query string if present
if "?" in reference:
    reference, query_string = reference.split("?", 1)
    parsed_params = parse_qs(query_string)
    # Merge with -p params (prefer -p)
    final_params = {**parsed_params, **params}
else:
    final_params = params
```

**Step 2: Deprecation warning**
```
Warning: Query string syntax (@api/source?param=value) is deprecated.
Use: jn cat @api/source -p param=value
```

**Step 3: Remove query string support** (v1.0)

---

## Special Cases & Edge Cases

### Case 1: Pagination (HTTP-specific, not parameterizable)

**Problem:**
```bash
jn cat "@genomoncology/alterations?page=2"
```
Hard to model as profile parameter (pagination is runtime state).

**Solution:** Still use -p
```bash
jn cat @genomoncology/alterations -p page=2
```

---

### Case 2: Array Parameters

**Problem:**
```bash
# Multiple genes:
jn cat @genomoncology/alterations -p gene=BRAF -p gene=EGFR
# → ?gene=BRAF&gene=EGFR (HTTP allows duplicate keys)
```

**Solution:** Support multiple -p with same key
```python
# Parse params allowing duplicates
params = {}
for p in param:
    key, value = p.split("=", 1)
    if key in params:
        # Convert to list
        if not isinstance(params[key], list):
            params[key] = [params[key]]
        params[key].append(value)
    else:
        params[key] = value

# HTTP resolver handles lists
# {"gene": ["BRAF", "EGFR"]} → ?gene=BRAF&gene=EGFR
```

---

### Case 3: Complex Filters (JSON values)

**Problem:**
```bash
# MongoDB-style filter:
jn cat @myapi/data -p filter='{"age": {"$gt": 25}}'
```

**Solution:** Pass JSON string as value
```python
# Profile can parse JSON params if needed
```

---

## Comparison Table

| Criterion | Query String (?) | -p Pattern | Winner |
|-----------|-----------------|------------|--------|
| Consistency with JN | ❌ New syntax | ✅ Existing | **-p** |
| HTTP familiarity | ✅ curl-like | ❌ Less obvious | ? |
| Shell quoting | ❌ Required | ✅ Not needed | **-p** |
| Verbosity | ✅ Compact | ❌ More chars | ? |
| Extensibility | ❌ HTTP-only | ✅ Generic | **-p** |
| Implementation | ⚠️ Custom parser | ✅ Reuse existing | **-p** |
| Documentation | ⚠️ Explain both | ✅ One pattern | **-p** |

**Score: -p Pattern wins 5-2**

---

## Final Recommendation

**Use -p pattern for HTTP query parameters.**

**Rationale:**

1. **Consistency > Brevity:** JN is a Unix-style CLI tool. Unix CLIs use flags (-p, --param) for options, not protocol-specific syntax.

2. **Separation of Concerns:**
   - Profile reference: `@api/source` (what to fetch)
   - Parameters: `-p key=value` (how to filter)
   - Clear distinction between identity and configuration

3. **Extensibility:** -p pattern works for any future profile type (SQL, GraphQL, etc.), not just HTTP.

4. **Implementation:** Reuse existing parameter infrastructure (parser, substitution, validation).

5. **Migration:** Can support query string temporarily for backward compat, then deprecate.

---

## Action Items

- [ ] Add `-p/--param` to `jn cat` command
- [ ] Update `resolve_profile_reference()` to accept `params` dict
- [ ] HTTP resolver builds query string from params
- [ ] Update documentation to use `-p` pattern
- [ ] Add deprecation warning for query string syntax
- [ ] Update spec/workflows/genomoncology-examples.md with new syntax

---

## Open Questions

1. **Should we support both syntaxes long-term?**
   - Recommendation: No. Deprecate query string.

2. **How to handle profile-specific param validation?**
   - Example: `alterations.json` declares `params: ["gene", "mutation_type"]`
   - Framework could validate params against profile schema
   - Out of scope for initial implementation

3. **Should -p be available on all commands?**
   - `jn cat` - YES (for HTTP sources)
   - `jn filter` - Already has it (for jq profiles)
   - `jn put` - Maybe? (for format profiles like CSV dialect)
   - Recommendation: Add to `cat` now, evaluate others later

---

## Appendix: Implementation Example

**Before (documented but not working):**
```bash
jn cat "@genomoncology/alterations?gene=BRAF&mutation_type=Missense" | \
  jn filter '@genomoncology/extract-alterations' | \
  jn put --plugin table - --tablefmt grid
```

**After (recommended):**
```bash
jn cat @genomoncology/alterations -p gene=BRAF -p mutation_type=Missense | \
  jn filter '@genomoncology/extract-alterations' | \
  jn put --plugin table --tablefmt grid -
```

**Comparison:**
- Before: 1 quoted arg, query string parsing
- After: 2 params, no quotes, uses existing -p infrastructure
- Verbosity: +13 chars (`-p ` × 2, -2 from quotes)
- Clarity: Better (clear param names)
