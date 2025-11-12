# Universal Addressability Strategy

**Status:** Final Design for v5
**Date:** 2025-11-12
**Decision:** Clean rip-and-replace (no migration, no deprecation)

---

## Executive Summary

This document defines the **universal addressability system** for JN v5, consolidating file references, URLs, protocols, profiles, stdin/stdout, and parameters into a single coherent design.

**Core Principles:**
1. **Query string syntax** (`?a=b&c=d`) for all parameters - no `-p` pollution
2. **@ symbol** for profiles (`@api/source`) and plugin references (`@plugin`)
3. **Protocol://** for explicit protocols (`http://`, `s3://`, `gmail://`)
4. **Multi-argument cat** - concatenate multiple sources naturally
5. **Stdin/stdout** addressed as `-` with explicit format hints
6. **Table format** via query params (`?table_fmt=grid`)
7. **Two-stage resolution** - protocol + format (unchanged)

---

## 1. Addressing Syntax Reference

### 1.1 File Paths

**Local files** - simple, extension-based auto-detection:

```bash
jn cat data.csv                    # Local CSV file
jn cat /absolute/path/data.json    # Absolute path
jn cat ./relative/data.yaml        # Relative path
jn cat "files with spaces.xlsx"    # Quoted paths
```

**Auto-detection:** Registry matches by extension (`.csv` → `csv_`, `.json` → `json_`)

### 1.2 Protocol URLs

**Explicit protocols** - `protocol://` triggers protocol plugin:

```bash
jn cat "http://example.com/data.csv"                    # HTTP + CSV
jn cat "s3://bucket/key.json"                           # S3 + JSON
jn cat "gmail://me/messages?from=boss"                  # Gmail protocol
jn cat "ftp://server/file.xlsx"                         # FTP + XLSX
```

**Two-stage resolution:**
1. Protocol: `http://` → `http_` plugin
2. Format: `.csv` extension → `csv_` plugin (for binary formats)

**For binary formats:**
```bash
jn cat "http://example.com/data.xlsx"
# Becomes: http_ (download) | xlsx_ (parse)
# Implementation: curl | uv run xlsx_.py --mode read
```

**For text formats:**
```bash
jn cat "http://example.com/data.json"
# Single stage: http_ plugin handles download + parsing
```

### 1.3 Profile References

**HTTP API profiles** - `@api/source`:

```bash
jn cat "@genomoncology/alterations"                     # Basic profile
jn cat "@genomoncology/alterations?gene=BRAF"           # With query params
jn cat "@genomoncology/alterations?gene=BRAF&limit=10"  # Multiple params
jn cat "@github/repos?org=anthropics"                   # GitHub API
```

**Resolution:**
```
@genomoncology/alterations
  ↓
Load: profiles/http/genomoncology/_meta.json (base_url, headers)
      + profiles/http/genomoncology/alterations.json (path, method)
  ↓
Build URL: base_url + path + query string
  ↓
Result: https://pwb-demo.genomoncology.io/api/alterations?gene=BRAF
```

**Filter profiles** - `@namespace/name`:

```bash
jn cat data.json | jn filter "@builtin/pivot?row=product&col=month"
jn cat data.json | jn filter "@analytics/custom?by=status"
jn cat data.json | jn filter "@genomoncology/extract-hgvs"
```

**Resolution:**
```
@builtin/pivot?row=product&col=month
  ↓
Load: profiles/jq/builtin/pivot.jq
  ↓
Substitute: $row → "product", $col → "month"
  ↓
Result: jq query with parameters replaced
```

### 1.4 Plugin References

**Direct plugin invocation** - `@plugin_name`:

```bash
jn cat data.csv --output "@json"      # Use json_ plugin explicitly
jn cat data.json --output "@table"    # Use table_ plugin
jn filter "@jq" '.[] | select(.active)'  # Use jq_ plugin directly
```

**Resolution:**
```
@json
  ↓
Check: Does profile "json" exist? NO
  ↓
Check: Does plugin "json_" exist? YES
  ↓
Use: json_ plugin
```

**Precedence:** Profiles take precedence over plugins (profiles are more specific).

### 1.5 Stdin/Stdout

**Stdin** - use `-` with optional format hint:

```bash
# Auto-detect format from content
echo '{"a":1}' | jn cat - | jn put output.csv

# Explicit format hint via query string
cat data.csv | jn cat "-?fmt=csv" | jn put output.json

# Alternative: Use --plugin flag (for backwards compatibility)
cat data.csv | jn cat - --plugin csv | jn put output.json
```

**Stdout** - use `-` or `stdout`:

```bash
jn cat data.csv | jn put -                           # Stdout (NDJSON)
jn cat data.csv | jn put "-?fmt=table&table_fmt=grid"  # Formatted table
jn cat data.csv | jn put stdout                      # Explicit stdout
```

**Special handling for stdin:**
- `-` without format hint → Try JSON/NDJSON auto-detection
- `-?fmt=csv` → Force CSV parsing
- `-?fmt=table` → Parse as table
- Detection errors → Helpful message suggesting format hint

---

## 2. Query String Parameters

### 2.1 Syntax

**URL query string syntax** - familiar and self-contained:

```bash
jn cat "@api/source?key=value&foo=bar"
```

**Must be quoted** (shell metacharacters `?` and `&`):

```bash
jn cat "@api/source?gene=BRAF"           # ✅ Quoted
jn cat @api/source?gene=BRAF             # ❌ Shell interprets ? and &
```

### 2.2 Multiple Values

**Same key multiple times** - list values:

```bash
jn cat "@api/data?gene=BRAF&gene=EGFR"
# → {"gene": ["BRAF", "EGFR"]}
# → URL: https://api.com/data?gene=BRAF&gene=EGFR
```

### 2.3 Special Parameters

**Reserved query params** for framework (not passed to profiles):

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `fmt` | Force format plugin | `-?fmt=csv` |
| `table_fmt` | Table output format | `output.table?table_fmt=grid` |
| `plugin` | Explicit plugin | `data.csv?plugin=csv_` |

**All other params** passed through to profiles/plugins.

### 2.4 Implementation: Parsing

**In `jn cat`:**

```python
def cat(ctx, input_file):
    """Parse query string from input reference."""
    params = {}
    source_ref = input_file

    # Check for query string
    if "?" in input_file:
        source_ref, query_string = input_file.split("?", 1)

        # Parse query string
        from urllib.parse import parse_qs
        parsed_params = parse_qs(query_string)

        # Flatten single values, keep lists for multiple
        for key, values in parsed_params.items():
            params[key] = values[0] if len(values) == 1 else values

    # Extract special params
    fmt = params.pop("fmt", None)
    plugin = params.pop("plugin", None)
    table_fmt = params.pop("table_fmt", None)

    # Pass remaining params to profile resolver
    read_source(source_ref, params=params, fmt=fmt, plugin=plugin)
```

---

## 3. Table Format Configuration

### 3.1 Current Problem

**Hardcoded in `put.py`:**

```python
# ❌ Only works for table plugin
plugin_config={"tablefmt": tablefmt} if plugin == "table" else None
```

**Should be generic:**

```python
# ✅ Works for any plugin config
plugin_config=parse_plugin_config(query_params)
```

### 3.2 Solution: Query String Config

**Via query params:**

```bash
jn cat data.json | jn put "output.table?table_fmt=grid"
jn cat data.json | jn put "output.table?table_fmt=grid&maxcolwidths=20"
jn cat data.json | jn put "output.csv?delimiter=;"
jn cat data.json | jn put "-?fmt=table&table_fmt=markdown"
```

**Via `--plugin` with query string:**

```bash
jn cat data.json | jn put - --plugin "table?table_fmt=grid"
```

### 3.3 Implementation: Generic Config

**Remove hardcoded table logic:**

```python
def put(ctx, output_file):
    """Parse query string for ANY plugin config."""
    # Parse query string
    dest, query_string = output_file.split("?", 1) if "?" in output_file else (output_file, "")

    # Parse into dict
    from urllib.parse import parse_qs
    params = parse_qs(query_string)
    plugin_config = {k: v[0] if len(v) == 1 else v for k, v in params.items()}

    # Extract special params
    fmt = plugin_config.pop("fmt", None)
    explicit_plugin = plugin_config.pop("plugin", None)

    # Pass remaining config to plugin
    write_destination(dest, plugin_name=explicit_plugin, plugin_config=plugin_config)
```

**Plugin receives config via command line:**

```bash
# Example: table plugin with config
uv run --script table_.py --mode write --table_fmt grid --maxcolwidths 20
```

**Plugin argument parsing:**

```python
# In table_.py
parser = argparse.ArgumentParser()
parser.add_argument("--mode", required=True)
parser.add_argument("--table_fmt", default="simple")
parser.add_argument("--maxcolwidths", type=int, default=None)
parser.add_argument("--showindex", type=bool, default=True)
args = parser.parse_args()

# Use args.table_fmt, args.maxcolwidths, etc.
```

---

## 4. Multi-File Concatenation

### 4.1 Motivation

**Unix `cat` concatenates** - JN should too:

```bash
# Unix cat
cat file1.txt file2.txt file3.txt > combined.txt

# JN cat (currently doesn't work)
jn cat file1.csv file2.csv file3.csv | jn put combined.json
```

### 4.2 Syntax

**Multiple arguments:**

```bash
jn cat file1.csv file2.json file3.yaml | jn put combined.json
jn cat local.csv "@api/remote?limit=100" | jn filter '.active'
jn cat "@gmail/inbox?from=boss" "@api/tickets?status=open" local.csv
jn cat data/*.csv | jn put combined.json  # Shell glob expansion
```

### 4.3 Behavior

**Sequential concatenation:**
1. Read file1 → NDJSON stream
2. Read file2 → NDJSON stream (append)
3. Read file3 → NDJSON stream (append)

**All output goes to stdout** (NDJSON concatenated).

**Error handling:**
- If any file fails, stop and error
- No partial output on error (buffer? or accept partial?)

### 4.4 Implementation

**Update CLI:**

```python
@click.command()
@click.argument("input_files", nargs=-1, required=True)  # Multiple args
def cat(ctx, input_files):
    """Read one or more files and output NDJSON to stdout."""
    for input_file in input_files:
        # Parse query string
        source_ref, params = parse_address(input_file)

        # Read and output
        read_source(source_ref, params=params, output_stream=sys.stdout)
```

**Edge cases:**
- Empty list → Error "No input files specified"
- Single file → Same as current behavior
- Multiple files → Sequential concatenation

---

## 5. Profile vs Plugin Resolution

### 5.1 Ambiguity Problem

**Both profiles and plugins use `@` syntax:**

```bash
jn cat "@genomoncology/alterations"  # Profile reference
jn filter "@builtin/pivot"           # Profile reference (jq)
jn cat data.json --output "@table"   # Plugin reference?
```

**How to distinguish?**

### 5.2 Resolution Strategy

**Check profiles first, fallback to plugins:**

```
Input: @something/name
  ↓
1. Check if profile exists: profiles/{plugin}/something/name.*
  ↓ NO
2. Check if plugin exists: {plugin}_
  ↓ YES
3. Use plugin
```

**Example:**

```bash
# This is a profile (profiles/http/genomoncology/alterations.json exists)
jn cat "@genomoncology/alterations"

# This is a plugin (no profile "json", but plugin "json_" exists)
jn cat data.csv | jn put - --plugin @json

# This is a profile (profiles/jq/builtin/pivot.jq exists)
jn filter "@builtin/pivot"
```

### 5.3 Explicit Plugin Reference

**To force plugin (skip profile check):**

```bash
# Option 1: Use plugin name directly (no @)
jn cat data.csv --plugin json

# Option 2: Use @ but no namespace (interpreted as plugin)
jn cat data.csv --plugin @json

# Option 3: Special syntax @plugin:name (future)
jn cat data.csv --plugin @plugin:json
```

**Current decision:** Options 1 and 2 work identically (profiles checked first, then plugins).

### 5.4 Namespace Conventions

**Avoid collisions with naming:**

| Type | Pattern | Example |
|------|---------|---------|
| HTTP Profile | `@api/source` | `@genomoncology/alterations` |
| Filter Profile | `@namespace/name` | `@builtin/pivot`, `@analytics/custom` |
| Plugin | `@name` (no slash) | `@json`, `@csv`, `@table` |

**Guideline:** Profiles use `/` separator, plugins don't.

---

## 6. Protocol vs Profile vs Plugin

### 6.1 Three Addressing Modes

**Summary table:**

| Type | Syntax | Example | Detection |
|------|--------|---------|-----------|
| **File** | `path` | `data.csv` | No special prefix |
| **Protocol** | `protocol://` | `http://api.com/data.json` | Contains `://` |
| **Profile** | `@api/source` | `@genomoncology/alterations` | Starts with `@`, contains `/` |
| **Plugin** | `@name` | `@json`, `@table` | Starts with `@`, no `/` |

### 6.2 Detection Algorithm

```python
def detect_address_type(address: str) -> str:
    """Detect address type from syntax."""
    if "://" in address:
        return "protocol"
    elif address.startswith("@"):
        if "/" in address:
            return "profile"
        else:
            return "plugin"
    elif address in ("-", "stdin"):
        return "stdin"
    elif address in ("stdout",):
        return "stdout"
    else:
        return "file"
```

### 6.3 Profile vs Protocol Relationship

**Profiles can resolve to protocol URLs:**

```bash
jn cat "@genomoncology/alterations"
  ↓ Profile resolution
"https://pwb-demo.genomoncology.io/api/alterations"
  ↓ Protocol detection
http_ plugin
```

**This is intentional and powerful:**
- Profile abstracts authentication, base URL, path structure
- Protocol handles actual fetching
- User doesn't need to know underlying URL

### 6.4 Special Case: Gmail

**Gmail has both profile and protocol:**

```bash
# Profile reference (user-friendly)
jn cat "@gmail/inbox?from=boss"
  ↓
Profile resolves to protocol URL:
gmail://me/messages?from=boss&is=unread
  ↓
Protocol plugin (gmail_) handles OAuth + fetching

# Direct protocol URL (advanced)
jn cat "gmail://me/messages?q=from:boss"
  ↓
Gmail plugin invoked directly
```

**Why both?**
- **Profile** - user-friendly, handles defaults, parameter mapping
- **Protocol** - direct access, full Gmail API control

---

## 7. Code Changes: Rip and Replace

### 7.1 Remove `-p` Flag

**Files to change:**

1. **`src/jn/cli/commands/cat.py`**
   ```python
   # REMOVE:
   @click.option("--param", "-p", multiple=True, help="...")

   # REMOVE: Parameter parsing loop
   params = {}
   for p in param:
       key, value = p.split("=", 1)
       ...
   ```

2. **`src/jn/cli/commands/filter.py`**
   ```python
   # REMOVE:
   @click.option("--param", "-p", multiple=True, help="...")
   ```

3. **`src/jn/core/pipeline.py`**
   - Keep `params` argument (populated from query string, not `-p`)
   - No changes needed to function signatures

**Tests to update:**
- `tests/profiles/test_http_profiles.py` - Replace `-p` with query string syntax
- Any integration tests using `-p` flags

**Docs to update:**
- All examples in spec docs
- README examples
- CLAUDE.md examples

### 7.2 Add Query String Parsing

**Files to change:**

1. **`src/jn/cli/commands/cat.py`**
   ```python
   def cat(ctx, input_files):  # Now accepts multiple files
       """Read files and output NDJSON to stdout."""
       for input_file in input_files:
           # Parse query string
           source_ref, params = _parse_address_with_query(input_file)

           # Read source
           read_source(source_ref, params=params, output_stream=sys.stdout)
   ```

2. **`src/jn/cli/commands/put.py`**
   ```python
   def put(ctx, output_file):
       """Read NDJSON from stdin and write to file."""
       # Parse query string for config
       dest, plugin_config = _parse_address_with_query(output_file)

       # Extract special params
       fmt = plugin_config.pop("fmt", None)
       plugin_name = plugin_config.pop("plugin", None)

       write_destination(dest, plugin_name=plugin_name,
                        plugin_config=plugin_config if plugin_config else None)
   ```

3. **New utility function** (add to `src/jn/util.py` or in commands):
   ```python
   from urllib.parse import parse_qs

   def parse_address_with_query(address: str) -> Tuple[str, Dict]:
       """Parse address and extract query string params.

       Args:
           address: May contain query string (e.g., "@api/src?key=val")

       Returns:
           Tuple of (address_without_query, params_dict)
       """
       if "?" not in address:
           return address, {}

       ref, query_string = address.split("?", 1)
       parsed = parse_qs(query_string)

       # Flatten single values, keep lists for multiple
       params = {}
       for key, values in parsed.items():
           params[key] = values[0] if len(values) == 1 else values

       return ref, params
   ```

### 7.3 Remove Table Format Hardcoding

**Files to change:**

1. **`src/jn/cli/commands/put.py`**
   ```python
   # REMOVE:
   @click.option("--tablefmt", default="simple", help="Table format for table plugin")

   # REMOVE:
   plugin_config={"tablefmt": tablefmt} if plugin in ("table", "table_") else None

   # REPLACE WITH:
   # Parse plugin_config from query string (see 7.2 above)
   ```

2. **`src/jn/core/pipeline.py`**
   ```python
   def write_destination(dest, ..., plugin_config=None):
       """Plugin config now comes from query string."""
       # Build command with config options (ALREADY EXISTS)
       cmd = ["uv", "run", "--script", plugin.path, "--mode", "write"]

       if plugin_config:
           for key, value in plugin_config.items():
               cmd.extend([f"--{key}", str(value)])
   ```

**No changes needed** - generic config handling already exists!

### 7.4 Multi-File Cat Support

**Files to change:**

1. **`src/jn/cli/commands/cat.py`**
   ```python
   # CHANGE:
   @click.argument("input_file")  # OLD: single file

   # TO:
   @click.argument("input_files", nargs=-1, required=True)  # NEW: multiple files

   def cat(ctx, input_files):
       for input_file in input_files:
           # Process each file
           ...
   ```

**Edge cases to handle:**
- Zero files → Error message
- One file → Works as before (backwards compatible)
- Multiple files → Sequential concatenation

### 7.5 Stdin/Stdout Format Hints

**Files to change:**

1. **`src/jn/core/pipeline.py`**
   ```python
   def read_source(source, ..., params=None):
       """Read source with optional format hint from params."""
       # Check for stdin
       if source in ("-", "stdin"):
           # Check for format hint in params
           fmt = params.get("fmt") if params else None

           if fmt:
               # Use explicit format plugin
               plugin_name = _resolve_plugin_name(fmt, plugins)
           else:
               # Try auto-detection (JSON/NDJSON)
               # This is new functionality
               plugin_name = _auto_detect_stdin_format(input_stream)
   ```

2. **New function:**
   ```python
   def _auto_detect_stdin_format(stream) -> str:
       """Auto-detect format from stdin content.

       Try to detect JSON/NDJSON from first line.
       Raise helpful error if detection fails.
       """
       # Read first line
       first_line = stream.readline()

       # Try parsing as JSON
       try:
           json.loads(first_line)
           # Success - looks like NDJSON
           return "json_"
       except json.JSONDecodeError:
           # Not JSON - need format hint
           raise PipelineError(
               "Cannot auto-detect stdin format. "
               "Use format hint: jn cat '-?fmt=csv' or jn cat - --plugin csv"
           )
   ```

### 7.6 Files to Delete

**None!** All files stay, just modified.

**Old API already removed:**
- `HTTPProfile` class (doesn't exist)
- `load_profile()` function (doesn't exist)

**Test cleanup needed:**
- Fix `tests/profiles/test_http_profiles.py` - uses old API

---

## 8. Migration: None Required

### 8.1 Breaking Changes

**This is a clean rip-and-replace:**

| Old Syntax | New Syntax | Breaking? |
|------------|------------|-----------|
| `jn cat @api/src -p gene=BRAF` | `jn cat "@api/src?gene=BRAF"` | ✅ YES |
| `jn put --tablefmt grid -` | `jn put "-?table_fmt=grid"` | ✅ YES |
| `jn filter @pivot -p row=x` | `jn filter "@pivot?row=x"` | ✅ YES |

**No backwards compatibility:**
- No support for `-p` flags
- No support for `--tablefmt` flag
- Clean break for simpler codebase

### 8.2 Documentation Updates

**Update all docs to new syntax:**

1. **README.md** - All examples
2. **CLAUDE.md** - All examples
3. **spec/design/*.md** - All specs
4. **tests/** - All tests
5. **jn_home/profiles/*/README.md** - Profile docs (if any)

### 8.3 Error Messages

**Helpful errors for old syntax:**

```python
# In cat.py
@click.option("--param", "-p", ...)  # Add back temporarily
def cat(ctx, input_files, param):
    if param:
        raise click.ClickException(
            "The -p flag is no longer supported. "
            "Use query string syntax instead:\n"
            '  Old: jn cat @api/src -p gene=BRAF\n'
            '  New: jn cat "@api/src?gene=BRAF"'
        )
```

**Same for `--tablefmt`:**

```python
# In put.py
@click.option("--tablefmt", ...)  # Add back temporarily
def put(ctx, output_file, tablefmt):
    if tablefmt:
        raise click.ClickException(
            "The --tablefmt flag is no longer supported. "
            "Use query string syntax instead:\n"
            '  Old: jn put --tablefmt grid -\n'
            '  New: jn put "-?table_fmt=grid"'
        )
```

**After grace period:** Remove these options entirely (just error on unknown flags).

---

## 9. Examples: Before and After

### 9.1 HTTP API Profiles

**Before:**
```bash
jn cat @genomoncology/alterations -p gene=BRAF -p limit=10
jn cat @github/repos -p org=anthropics -p type=public
```

**After:**
```bash
jn cat "@genomoncology/alterations?gene=BRAF&limit=10"
jn cat "@github/repos?org=anthropics&type=public"
```

### 9.2 Table Output

**Before:**
```bash
jn cat data.json | jn put --plugin table --tablefmt grid -
jn cat data.json | jn put --plugin table --tablefmt markdown stdout
```

**After:**
```bash
jn cat data.json | jn put "-?table_fmt=grid"
jn cat data.json | jn put "stdout?table_fmt=markdown"
```

### 9.3 Filter Profiles

**Before:**
```bash
jn cat data.json | jn filter @builtin/pivot -p row=product -p col=month
jn cat data.json | jn filter @analytics/custom -p by=status
```

**After:**
```bash
jn cat data.json | jn filter "@builtin/pivot?row=product&col=month"
jn cat data.json | jn filter "@analytics/custom?by=status"
```

### 9.4 Multi-File Cat (NEW)

**Before:**
```bash
# Not possible
```

**After:**
```bash
jn cat file1.csv file2.json file3.yaml | jn put combined.json
jn cat local.csv "@genomoncology/alterations?gene=BRAF" | jn filter '.active'
jn cat "@gmail/inbox?from=boss" "@api/tickets?status=open" | jn put urgent.json
```

### 9.5 Stdin with Format Hint (NEW)

**Before:**
```bash
cat data.csv | jn cat -  # Might fail if auto-detection doesn't work
```

**After:**
```bash
cat data.csv | jn cat "-?fmt=csv"  # Explicit format
cat data.json | jn cat -           # Auto-detect (JSON/NDJSON)
```

### 9.6 Mixing Everything (NEW)

**Before:**
```bash
# Not possible in one pipeline
```

**After:**
```bash
# Concatenate local file + HTTP profile + protocol URL + Gmail
jn cat \
  local.csv \
  "@genomoncology/alterations?gene=BRAF" \
  "http://api.example.com/data.json" \
  "@gmail/inbox?from=boss&newer_than=7d" \
  | jn filter '@builtin/flatten' \
  | jn put "-?table_fmt=grid"
```

---

## 10. Implementation Checklist

### Phase 1: Core Changes (Breaking)

- [ ] **Remove `-p` flag** from `cat.py` and `filter.py`
- [ ] **Remove `--tablefmt` flag** from `put.py`
- [ ] **Add query string parsing** utility function
- [ ] **Update `cat` command** to accept multiple files (`nargs=-1`)
- [ ] **Update `cat` command** to parse query strings
- [ ] **Update `put` command** to parse query strings for plugin config
- [ ] **Update `filter` command** to parse query strings

### Phase 2: New Features

- [ ] **Stdin format hints** - handle `-?fmt=csv`
- [ ] **Stdout format hints** - handle `stdout?table_fmt=grid`
- [ ] **Multi-file concatenation** - loop over multiple input files
- [ ] **Profile vs plugin resolution** - check profiles first, fallback to plugins

### Phase 3: Cleanup

- [ ] **Fix test pollution** - update `test_http_profiles.py` to use new API
- [ ] **Update all tests** - replace `-p` with query strings
- [ ] **Update all docs** - README, CLAUDE.md, spec/*.md
- [ ] **Update examples** - all code samples
- [ ] **Remove old test fixtures** - if any used old syntax

### Phase 4: Polish

- [ ] **Error messages** - helpful migration messages for old syntax
- [ ] **Validation** - query param validation (optional, warn on typos)
- [ ] **Shell completion** - add quotes for query string syntax
- [ ] **Performance** - ensure query parsing doesn't add overhead

---

## 11. Future Enhancements

### 11.1 OpenAPI Generation (Later)

**Generate profiles from OpenAPI specs:**

```bash
jn profile import openapi https://api.example.com/openapi.json --name myapi
# Creates: profiles/http/myapi/_meta.json + {endpoint}.json files
```

### 11.2 OAuth Token Refresh (Later)

**Automatic token refresh for HTTP profiles:**

```json
// profiles/http/gmail/_meta.json
{
  "base_url": "https://gmail.googleapis.com",
  "auth": {
    "type": "oauth2",
    "token_file": "~/.jn/tokens/gmail.json",
    "refresh_url": "https://oauth2.googleapis.com/token",
    "client_id": "${GMAIL_CLIENT_ID}",
    "client_secret": "${GMAIL_CLIENT_SECRET}"
  }
}
```

### 11.3 Profile CLI (Later)

**Implement profile discovery commands:**

```bash
jn profile list                    # List all profiles
jn profile info @api/source        # Show profile details
jn profile test @api/source        # Test profile connection
jn profile tree                    # Show profile hierarchy
```

### 11.4 Path Variables (Later)

**Template variables in profile paths:**

```json
// profiles/http/github/repo.json
{
  "path": "/repos/{owner}/{repo}",
  "params": ["owner", "repo"]
}
```

```bash
jn cat "@github/repo?owner=anthropics&repo=claude"
# Resolves to: https://api.github.com/repos/anthropics/claude
```

---

## 12. Decision Record

### Decision: Query String Syntax

**Chosen:** `jn cat "@api/src?gene=BRAF&limit=10"`

**Rejected:** `jn cat @api/src -p gene=BRAF -p limit=10`

**Rationale:**
1. ✅ Self-contained - entire address in one string
2. ✅ Familiar - URL syntax everyone knows
3. ✅ Enables multi-file cat without flag pollution
4. ✅ Composable - mix files, URLs, profiles naturally
5. ⚠️ Requires quoting - but so do URLs and globs already
6. ✅ Shell completion can auto-quote

### Decision: Multi-File Cat

**Chosen:** `jn cat file1.csv file2.json file3.yaml`

**Rationale:**
1. ✅ Consistent with Unix `cat` behavior
2. ✅ Natural composition of data sources
3. ✅ Works seamlessly with query string params
4. ✅ Enables powerful pipelines

### Decision: Clean Rip-and-Replace

**Chosen:** No migration, no deprecation, breaking changes OK

**Rationale:**
1. ✅ JN is pre-1.0, early stage
2. ✅ Clean codebase, no legacy baggage
3. ✅ Easier to maintain going forward
4. ✅ Clear, consistent API from the start
5. ⚠️ Breaks existing usage - acceptable at this stage

### Decision: Query Params for Plugin Config

**Chosen:** `jn put "-?table_fmt=grid"`

**Rationale:**
1. ✅ Consistent with other addressing
2. ✅ Removes hardcoded table logic
3. ✅ Extensible to any plugin config
4. ✅ Clear, declarative syntax

---

## 13. Summary

**Universal Addressability Syntax:**

```
<address>[?<params>]

Where <address> is:
  - file.ext          → Local file
  - protocol://path   → Protocol URL
  - @api/source       → Profile reference
  - @plugin           → Plugin reference
  - -                 → Stdin
  - stdout            → Stdout

Where <params> is:
  key=value&key2=value2

Special params:
  fmt=csv             → Force format
  plugin=csv_         → Force plugin
  table_fmt=grid      → Plugin config
```

**Resolution Order:**

1. **Protocol detection** - contains `://` → protocol plugin
2. **Profile resolution** - starts with `@`, contains `/` → profile lookup
3. **Plugin resolution** - starts with `@`, no `/` → plugin lookup
4. **File matching** - registry pattern matching by extension
5. **Stdin/stdout** - special handling for `-`, `stdin`, `stdout`

**Clean Break:**
- ✅ Remove `-p` flag
- ✅ Remove `--tablefmt` flag
- ✅ Add query string parsing
- ✅ Add multi-file support
- ✅ Unified, consistent addressing

**Result:** Simple, powerful, composable addressing system for JN v5.
