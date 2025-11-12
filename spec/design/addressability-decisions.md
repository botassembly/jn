# Addressability Design Decisions

**Date:** 2025-11-12
**Status:** Final
**Related:** universal-addressability-strategy.md, addressability-implementation-plan.md

---

## Your Questions Answered

### Q1: How do we address profiles and protocols?

**Answer:**

| Type | Syntax | Example | Use Case |
|------|--------|---------|----------|
| **Protocol** | `protocol://path` | `http://api.com/data.csv`<br>`s3://bucket/key.json`<br>`gmail://me/messages` | Explicit protocol access |
| **Profile** | `@api/source` | `@genomoncology/alterations`<br>`@gmail/inbox`<br>`@github/repos` | User-friendly API access |
| **Plugin** | `@name` (no `/`) | `@json`<br>`@table`<br>`@csv` | Direct plugin invocation |

**Profiles can resolve to protocols:**
```
@gmail/inbox
  ↓ Profile resolution
gmail://me/messages?in=inbox
  ↓ Protocol plugin
Gmail plugin fetches emails
```

---

### Q2: How does two-part resolution work (protocol + format)?

**Answer: It works correctly today! Just needs documentation.**

**For binary format URLs:**
```bash
jn cat "http://example.com/data.xlsx"
```

**Resolution:**
1. **Protocol detected:** `http://` → use `http_` or `curl`
2. **Format detected:** `.xlsx` extension → use `xlsx_` plugin
3. **Pipeline:** `curl http://... | uv run xlsx_.py --mode read`

**Implementation in `pipeline.py` (already works):**
```python
if _is_binary_format_url(source):
    # Two-stage pipeline
    ext = Path(urlparse(source).path).suffix  # .xlsx
    format_plugin = registry.match(f"file{ext}")  # xlsx_

    # curl streams bytes → format plugin buffers → streams NDJSON
    curl_proc = subprocess.Popen(["curl", "-sL", source], stdout=PIPE)
    reader = subprocess.Popen(["uv", "run", plugin.path, "--mode", "read"],
                             stdin=curl_proc.stdout, stdout=PIPE)
```

**For text format URLs:**
```bash
jn cat "http://example.com/data.json"
```

**Resolution:**
1. **Protocol detected:** `http://` → use `http_` plugin
2. **Format detection:** HTTP plugin auto-detects JSON/CSV/NDJSON from Content-Type
3. **Single stage:** `uv run http_.py --mode read "url"`

**Verdict: ✅ Two-part resolution works. No changes needed.**

---

### Q3: Should we use query strings (`?a=b&c=d`) or keep `-p`?

**Answer: Query strings. Remove `-p` entirely.**

**Rationale:**

| Aspect | Query String `?a=b` | `-p` Flag |
|--------|---------------------|-----------|
| Self-contained | ✅ Yes - entire address in one string | ❌ No - separate flags |
| Familiar | ✅ Yes - URL syntax everyone knows | ⚠️ Familiar to CLI users only |
| Multi-file cat | ✅ Enables `cat file1 file2 file3` | ❌ Ambiguous with multiple files |
| Composable | ✅ Mix files, URLs, profiles naturally | ❌ Flags pollute command line |
| Quoting | ⚠️ Must quote `"@api?a=b"` | ✅ No quoting needed |

**Decision: Query string wins despite quoting requirement.**

**Examples:**
```bash
# Query string (CHOSEN)
jn cat "@genomoncology/alterations?gene=BRAF&limit=10"
jn cat file1.csv "@api/remote?limit=100" file3.yaml

# -p flags (REJECTED)
jn cat @genomoncology/alterations -p gene=BRAF -p limit=10
jn cat file1.csv @api/remote -p limit=100 file3.yaml  # Ambiguous!
```

**Shell completion can auto-add quotes.**

---

### Q4: How to specify table format?

**Answer: Query string parameter `table_fmt=grid`**

**Remove:**
```bash
# OLD (remove)
jn cat data.json | jn put --tablefmt grid -
```

**Replace with:**
```bash
# NEW (use query string)
jn cat data.json | jn put "-?table_fmt=grid"
jn cat data.json | jn put "output.table?table_fmt=markdown"
jn cat data.json | jn put "-?table_fmt=grid&maxcolwidths=20"
```

**Implementation:**
1. Parse query string in `put` command
2. Extract `table_fmt` (and any other params)
3. Pass to plugin as `--table_fmt grid`
4. Plugin receives and uses it

**This generalizes to ANY plugin config:**
```bash
jn cat data.json | jn put "output.csv?delimiter=;"
jn cat data.json | jn put "output.yaml?indent=4"
```

**Current code issue:** Hardcoded table logic in `put.py`:
```python
# REMOVE THIS:
plugin_config={"tablefmt": tablefmt} if plugin == "table" else None

# REPLACE WITH:
plugin_config = parse_query_string(output_file)  # Generic for all plugins
```

---

### Q5: How to address stdin/stdout and specify format?

**Answer: Use `-` with optional `?fmt=` query parameter**

**Stdin:**
```bash
# Auto-detect (JSON/NDJSON only)
echo '{"a":1}' | jn cat - | jn put output.json

# Explicit format hint
cat data.csv | jn cat "-?fmt=csv" | jn put output.json

# Alternative (backwards compatibility)
cat data.csv | jn cat - --plugin csv | jn put output.json
```

**Stdout:**
```bash
# Plain NDJSON
jn cat data.csv | jn put -

# Formatted table
jn cat data.csv | jn put "-?table_fmt=grid"

# Or use "stdout" explicitly
jn cat data.csv | jn put "stdout?table_fmt=markdown"
```

**Implementation:**
```python
def read_source(source, ..., fmt=None):
    if source in ("-", "stdin"):
        if fmt:
            # Use explicit format plugin
            plugin_name = resolve_plugin(fmt)
        else:
            # Try auto-detect (JSON/NDJSON)
            # Error with helpful message if fails
```

---

### Q6: Should `cat` concatenate multiple files?

**Answer: YES! Critical feature, consistent with Unix.**

**Current state: Does NOT work (only accepts one file)**

**Desired behavior:**
```bash
# Concatenate multiple files
jn cat file1.csv file2.json file3.yaml | jn put combined.json

# Mix local and remote
jn cat local.csv "@api/remote?limit=100" | jn filter '.active'

# Complex composition
jn cat \
  data/*.csv \
  "@genomoncology/alterations?gene=BRAF" \
  "http://api.example.com/data.json" \
  | jn put combined.json
```

**Implementation:**
```python
# Change from:
@click.argument("input_file")  # Single file

# To:
@click.argument("input_files", nargs=-1, required=True)  # Multiple files

def cat(ctx, input_files):
    for input_file in input_files:
        read_source(input_file, ...)  # Process each sequentially
```

---

### Q7: Can `@` be used for both profiles and plugins?

**Answer: YES! Profiles checked first, plugins as fallback.**

**Resolution order:**
```
Input: @something/name
  ↓
1. Check if profile exists
   Search: profiles/{plugin}/something/name.*
  ↓ If found → Use profile
  ↓ If not found ↓
2. Check if plugin exists
   Search: plugins/{something}_*
  ↓ If found → Use plugin
  ↓ If not found ↓
3. Error: "Profile or plugin not found"
```

**Examples:**

```bash
# Profile (has slash)
jn cat "@genomoncology/alterations"
# → Searches profiles/http/genomoncology/alterations.json → FOUND → Use profile

# Plugin (no slash)
jn cat - --plugin @json
# → Searches profiles/json.* → NOT FOUND → Searches plugins/json_* → FOUND → Use plugin

# Another profile
jn filter "@builtin/pivot"
# → Searches profiles/jq/builtin/pivot.jq → FOUND → Use profile
```

**Naming convention to avoid collisions:**
- **Profiles:** Always use `/` separator (`@api/source`, `@ns/name`)
- **Plugins:** No slash (`@json`, `@csv`, `@table`)

---

### Q8: How does `@http/myAPI/myEndpoint` work?

**Answer: Doesn't exist today, but could work as profile hierarchy.**

**Current profile structure:**
```
profiles/http/{api}/{source}.json
```

**Your suggestion:**
```bash
jn cat "@http/myAPI/myEndpoint?a=b"
```

**Interpretation:**
- `@http` - profile system (not plugin)
- `myAPI` - API name
- `myEndpoint` - source name

**This is exactly what we have!**
```
@genomoncology/alterations
  ↓
profiles/http/genomoncology/alterations.json
```

**So your syntax already works:**
```bash
jn cat "@genomoncology/alterations?gene=BRAF"
# Same as:
jn cat "@http/genomoncology/alterations?gene=BRAF"  # Could support this too
```

**Extension idea (future):**

Allow explicit protocol prefix:
```bash
jn cat "@http/genomoncology/alterations?gene=BRAF"
jn cat "@gmail/inbox?from=boss"
jn cat "@s3/mybucket/mykey?region=us-west-2"
```

**Current: Optional prefix (implicit)**
**Future: Optional explicit prefix (clearer)**

**Decision: Current syntax is fine, explicit prefix optional enhancement.**

---

## What Code to Remove

### Remove Completely

1. **`-p` flag** from `cat.py` and `filter.py`
   - Lines 13-17 in cat.py
   - Lines 29-43 in cat.py (param parsing loop)
   - Same in filter.py

2. **`--tablefmt` flag** from `put.py`
   - Line 14 in put.py
   - Line 32 hardcoded config logic

3. **Old test imports** in `test_http_profiles.py`
   - `HTTPProfile` class (doesn't exist anyway)
   - `load_profile()` function (doesn't exist anyway)

### Keep (Don't Remove)

1. **`--plugin` flag** in `put.py` - useful for explicit overrides
2. **Profile resolution code** in `http.py` and `resolver.py` - works great
3. **Two-part resolution** in `pipeline.py` - works great
4. **Registry pattern matching** - works great

---

## What Code to Add

### New Files

1. **`src/jn/util.py`** (~100 lines)
   - `parse_address_with_query(address)` → (ref, params)
   - `extract_special_params(params)` → (special, remaining)

2. **`tests/util/test_util.py`** (~50 lines)
   - Tests for query string parsing

3. **These spec documents:**
   - `spec/design/universal-addressability-strategy.md` ✅ (already created)
   - `spec/design/addressability-implementation-plan.md` ✅ (already created)
   - `spec/design/addressability-decisions.md` ✅ (this file)

### Modified Files

1. **`src/jn/cli/commands/cat.py`**
   - Change `input_file` → `input_files` (nargs=-1)
   - Remove `-p` flag
   - Add query string parsing
   - Loop over multiple files

2. **`src/jn/cli/commands/put.py`**
   - Remove `--tablefmt` flag
   - Add query string parsing
   - Generic plugin config (remove hardcoding)

3. **`src/jn/cli/commands/filter.py`**
   - Remove `-p` flag
   - Add query string parsing

4. **`src/jn/core/pipeline.py`**
   - Add `fmt` parameter to `read_source()`
   - Add `explicit_plugin` parameter
   - Add `_read_stdin()` helper
   - Add `_auto_detect_stdin_format()` helper

5. **`tests/profiles/test_http_profiles.py`**
   - Fix imports (remove old API references)
   - Update test cases to use new API

6. **All test files using `-p`**
   - Replace with query string syntax

7. **Documentation files:**
   - README.md
   - CLAUDE.md
   - spec/design/*.md

---

## Migration Strategy

### No Migration - Clean Break

**This is pre-1.0 software. Breaking changes are acceptable.**

**Approach:**
1. ✅ Remove old syntax entirely (no compatibility layer)
2. ⚠️ Add helpful error messages temporarily:
   ```
   Error: The -p flag is no longer supported.
   Use query string syntax: "@api/src?gene=BRAF"
   ```
3. ⏸️ Remove error messages after 1-2 releases

**No deprecation warnings. No dual support. Clean rip-and-replace.**

---

## Questions Still Open

### None! All questions answered.

Your original questions:
- ✅ How to address profiles/protocols? → `@profile/source`, `protocol://`
- ✅ Two-part resolution working? → Yes, works great
- ✅ Use query strings? → Yes, remove `-p`
- ✅ Table format? → Query string `?table_fmt=grid`
- ✅ Stdin/stdout? → `-` with optional `?fmt=csv`
- ✅ Cat concatenation? → Yes, critical feature
- ✅ @ for profiles and plugins? → Yes, profiles first, then plugins
- ✅ What code to remove? → `-p` flag, `--tablefmt` flag, old test imports
- ✅ What code to add? → Query string parsing, multi-file support, stdin format hints

---

## Final Design Summary

```
# Addressing Syntax
file.csv                                    → File (registry match)
http://api.com/data.csv                     → Protocol + Format (two-stage)
@genomoncology/alterations                  → HTTP Profile
@builtin/pivot                              → Filter Profile (jq)
@json                                       → Plugin (direct)
-                                           → Stdin
stdout                                      → Stdout

# Parameters
@api/source?gene=BRAF&limit=10              → Query string
-?fmt=csv                                   → Format hint for stdin
-?table_fmt=grid                            → Plugin config
output.csv?delimiter=;                      → Plugin config

# Multi-file Concatenation
jn cat file1.csv file2.json file3.yaml      → Sequential concat

# Profile Resolution
@genomoncology/alterations?gene=BRAF
  ↓
profiles/http/genomoncology/_meta.json + alterations.json
  ↓
https://pwb-demo.genomoncology.io/api/alterations?gene=BRAF
  ↓
http_ plugin

# Two-Stage Resolution (Binary Formats)
http://example.com/data.xlsx
  ↓
curl | xlsx_ plugin
  ↓
NDJSON stream
```

---

## Implementation Priority

**Priority 1 (Core):**
1. Add `util.py` with query string parsing
2. Update `cat.py` - multi-file + query strings
3. Update `put.py` - query strings for config
4. Update `filter.py` - query strings for params

**Priority 2 (Cleanup):**
5. Fix `test_http_profiles.py` imports
6. Update all tests using `-p`
7. Add tests for new features

**Priority 3 (Documentation):**
8. Update README examples
9. Update CLAUDE.md examples
10. Update spec docs

**Priority 4 (Polish):**
11. Add helpful error messages for old syntax
12. Performance testing
13. Shell completion updates

---

## Success Metrics

**Must have:**
- ✅ All tests pass
- ✅ Query string syntax works for all examples
- ✅ Multi-file cat works
- ✅ Table config via query string works
- ✅ Stdin format hints work
- ✅ Old syntax shows helpful errors

**Nice to have:**
- Shell completion adds quotes automatically
- Performance unchanged (no regression)
- Documentation clear and complete

---

## Timeline

**Estimated effort:** 6-8 hours focused work

**Breakdown:**
- Code changes: 2-3 hours
- Test updates: 2-3 hours
- Documentation: 1 hour
- Testing/QA: 1 hour

**Confidence:** High - changes are well-defined, risks are low.
