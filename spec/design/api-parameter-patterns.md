# HTTP API Parameter Patterns

## Problem

How should users pass query parameters to HTTP API sources?

**Example:**
```bash
# Fetch BRAF alterations from GenomOncology API
jn cat @genomoncology/alterations ???
```

## Solution: Use -p Pattern

**Syntax:**
```bash
jn cat @genomoncology/alterations -p gene=BRAF -p mutation_type=Missense
```

**Rationale:**
1. **Consistent with JN:** `jn filter` already uses `-p` for profile parameters
2. **Generic:** Works for any profile type (HTTP, SQL, GraphQL, etc.), not just HTTP
3. **Simple:** No shell quoting required, reuses existing parameter infrastructure
4. **Clear:** Separates profile reference (`@api/source`) from parameters (`-p key=value`)

---

## Implementation

### 1. Add -p to cat Command

**File:** `src/jn/cli/commands/cat.py`

```python
@click.command()
@click.argument("input_file")
@click.option("--param", "-p", multiple=True, help="Profile parameter (key=value)")
@pass_context
def cat(ctx, input_file, param):
    """Read file and output NDJSON to stdout."""
    # Parse params
    params = {}
    for p in param:
        if "=" not in p:
            raise click.ClickException(f"Invalid parameter format: {p} (use key=value)")
        key, value = p.split("=", 1)

        # Support multiple values for same key (becomes list)
        if key in params:
            if not isinstance(params[key], list):
                params[key] = [params[key]]
            params[key].append(value)
        else:
            params[key] = value

    read_source(input_file, ctx.plugin_dir, ctx.cache_path,
                output_stream=sys.stdout, params=params)
```

---

### 2. Update HTTP Profile Resolver

**File:** `src/jn/profiles/http.py`

```python
def resolve_profile_reference(reference: str, params: dict = None) -> Tuple[str, dict]:
    """Resolve @api/source reference to URL and headers.

    Args:
        reference: Profile reference like "@genomoncology/alterations"
        params: Optional query parameters like {"gene": "BRAF", "mutation_type": "Missense"}

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
        # Validate against declared params (if any)
        declared_params = profile.get("params", [])
        if declared_params:
            # Separate declared vs ad hoc params
            declared = {k: v for k, v in params.items() if k in declared_params}
            ad_hoc = {k: v for k, v in params.items() if k not in declared_params}

            # Both are allowed - merge and build query string
            all_params = {**declared, **ad_hoc}
        else:
            # No declared params - all params are ad hoc (allowed)
            all_params = params

        # Build query string
        from urllib.parse import urlencode
        query_string = urlencode(all_params, doseq=True)  # doseq handles lists
        url = f"{url}?{query_string}"

    # Build headers
    headers = profile.get("headers", {})
    resolved_headers = {k: substitute_env_vars(v) for k, v in headers.items()}

    return url, resolved_headers
```

---

### 3. Update Pipeline to Pass Params

**File:** `src/jn/core/pipeline.py`

```python
def read_source(source: str, ..., params: dict = None):
    """Read a source file or URL and output NDJSON to stream.

    Args:
        params: Optional parameters for profile resolution (e.g., {"gene": "BRAF"})
    """
    if source.startswith("@"):
        url, headers = resolve_profile_reference(source, params)
        # ... rest of HTTP handling
```

---

## Profile Parameter Declaration

Profiles can optionally declare expected parameters:

**File:** `jn_home/profiles/http/genomoncology/alterations.json`

```json
{
  "path": "/alterations",
  "method": "GET",
  "type": "source",
  "params": ["gene", "mutation_type", "biomarker", "page", "limit"]
}
```

**Benefits:**
1. **Documentation:** Users know which params are supported
2. **Validation:** Framework can warn on typos (optional - don't error)
3. **Discovery:** `jn info @genomoncology/alterations` can show available params
4. **Ad hoc params still allowed:** Framework passes through undeclared params

---

## Parameter Types

### Simple Parameters
```bash
jn cat @genomoncology/alterations -p gene=BRAF
# → ?gene=BRAF
```

### Multiple Values (Arrays)
```bash
jn cat @api/data -p gene=BRAF -p gene=EGFR
# → ?gene=BRAF&gene=EGFR
```

**Implementation:** Multiple `-p` with same key creates list, `urlencode(params, doseq=True)` handles it.

### Complex Values (JSON)
```bash
jn cat @api/data -p 'filter={"age": {"$gt": 25}}'
# → ?filter=%7B%22age%22%3A...
```

**Implementation:** Pass as string, API handles JSON parsing.

---

## Future: jn info Command

**Show profile details including parameters:**

```bash
$ jn info @genomoncology/alterations

Profile: @genomoncology/alterations
Type: HTTP source
API: genomoncology
Source: alterations

Configuration:
  URL: https://${GENOMONCOLOGY_URL}/api/alterations
  Method: GET
  Headers: Authorization, Accept

Parameters (optional):
  gene          - Gene symbol (e.g., BRAF, EGFR)
  mutation_type - Type of mutation (e.g., Missense, Nonsense)
  biomarker     - Biomarker name
  page          - Page number for pagination
  limit         - Results per page

Example:
  jn cat @genomoncology/alterations -p gene=BRAF -p limit=10
```

**Implementation:**
- Read profile config
- Parse declared `params` array
- Show base URL, method, headers
- Display example usage

---

## Migration Notes

**No backwards compatibility.** This is the only way to pass parameters.

**Documentation updates needed:**
- spec/workflows/genomoncology-examples.md - Update all examples to use `-p`
- README.md - Document parameter pattern
- Profile design docs - Show parameter declaration

---

## Comparison

| Approach | Syntax | Notes |
|----------|--------|-------|
| ❌ Query string | `jn cat "@api/source?key=value"` | Rejected - HTTP-specific, requires quoting |
| ✅ -p pattern | `jn cat @api/source -p key=value` | **Chosen** - Generic, consistent with filter |
| ❌ JSON inline | `jn cat @api/source --params '{"key":"value"}'` | Rejected - Too verbose |

---

## Implementation Checklist

- [ ] Add `-p/--param` to `src/jn/cli/commands/cat.py`
- [ ] Update `src/jn/profiles/http.py` to accept and use `params` dict
- [ ] Update `src/jn/core/pipeline.py` to pass params through
- [ ] Add `params` field to profile schema (optional declaration)
- [ ] Update GenomOncology profile sources with declared params
- [ ] Update `spec/workflows/genomoncology-examples.md` with `-p` syntax
- [ ] Add tests for parameter passing
- [ ] Add tests for list parameters (multiple -p with same key)
- [ ] Document in README.md
- [ ] (Future) Implement `jn info` command to show profile params
