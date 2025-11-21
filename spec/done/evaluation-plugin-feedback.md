# JN Plugin Tool Evaluation & Recommendations

**Date:** 2025-11-21
**Evaluator:** Developer feedback from DuckDB plugin implementation
**Status:** Active - Requires Team Action

## Executive Summary

A developer built a DuckDB plugin for JN and provided valuable feedback on friction points. This document synthesizes their feedback and provides actionable recommendations to improve the developer and user experience.

## Developer Feedback Overview

### What Works Well ✅

1. **Clean Plugin Model** - PEP 723 + `uv run --script` keeps dependencies isolated
2. **Address Syntax** - The `address~format?params` syntax is great for agent discoverability
3. **Streaming Architecture** - Pipes + SIGPIPE propagation aligns with "constant memory" goal
4. **Built-in Helpers** - `jn head`, `jn filter`, profiles make shell-style pipelines expressive
5. **CLI Framing** - Easy to expose data to agents without bespoke Python wrappers

### Friction Points 🔧

1. **Format Detection Misses Common .txt TSVs**
   - Issue: CSV plugin doesn't match `.*\.txt$` files
   - Impact: "no plugin found" errors without obvious hint
   - Example: `jn cat data_clinical_patient.txt` fails

2. **Protocol Addresses are Brittle**
   - Issue: URLs like `duckdb://path?...` need exact quoting/encoding
   - Impact: Sometimes fails silently with no clear error
   - Example: Plugin invoked with no `--path` and fails silently

3. **Poor Error Messaging**
   - Issue: Error messages too terse ("plugin not found")
   - Impact: Users left guessing how to fix the problem
   - Need: Concise suggestions (e.g., "try ~csv" or "use duckdb://...?query=...")

4. **Param Handling Not Obvious**
   - Issue: Not clear how to pass named params from address string
   - Impact: Users don't know how to use `?query=...&param_name=value`
   - Need: Better documentation and error messages for malformed params

5. **Examples Bypass Golden Path**
   - Issue: Examples and helpers call plugins directly instead of using `jn cat ...`
   - Impact: Users bypass the intended architecture
   - Need: Stronger "golden path" docs and examples

---

## Detailed Recommendations

### 1. Fix .txt File Detection (High Priority)

**Problem:**
CSV plugin doesn't match `.txt` files, causing common TSV files to fail.

**Current Code:**
```python
# jn_home/plugins/formats/csv_.py
# [tool.jn]
# matches = [
#   ".*\\.csv$",
#   ".*\\.tsv$"
# ]
```

**Fix:**
```python
# [tool.jn]
# matches = [
#   ".*\\.csv$",
#   ".*\\.tsv$",
#   ".*\\.txt$"    # Add this line
# ]
```

**Test Case:**
```bash
# Should work after fix:
jn cat data_clinical_patient.txt
jn cat data.txt~csv?delimiter=tab
```

**Files to Modify:**
- `jn_home/plugins/formats/csv_.py` (line 7-10)

---

### 2. Improve Error Messages (High Priority)

**Problem:**
Error messages are terse and don't suggest solutions.

**Current Errors:**
```
No plugin found for: data.txt. Consider using format override: data.txt~<format>
Plugin not found for format: duckdb. Available plugins: csv_, json_, ...
```

**Improved Errors:**

```python
# For file pattern matching (src/jn/addressing/resolver.py:508-511)
# Current:
raise AddressResolutionError(
    f"No plugin found for: {source}. "
    f"Consider using format override: {source}~<format>"
)

# Improved:
ext = Path(source).suffix
suggestions = []
if ext in ('.txt', '.dat'):
    suggestions.append(f"try ~csv: {source}~csv")
elif ext in ('.db', '.duckdb'):
    suggestions.append(f"try duckdb://: duckdb://{source}?query=SELECT * FROM table_name")

suggestion_text = "\n  Suggestions:\n    " + "\n    ".join(suggestions) if suggestions else ""

raise AddressResolutionError(
    f"No plugin found for: {source}\n"
    f"  Consider using format override: {source}~<format>{suggestion_text}"
)
```

```python
# For protocol URLs (src/jn/addressing/resolver.py:459-462)
# Current:
raise AddressResolutionError(
    f"Plugin not found for protocol: {protocol}. "
    f"Available plugins: {', '.join(sorted(self._plugins.keys()))}"
)

# Improved:
common_protocols = {
    'duckdb': 'duckdb://path/to/file.duckdb?query=SELECT * FROM table',
    'sqlite': 'sqlite://path/to/file.db?query=SELECT * FROM table',
    'postgres': 'postgres://host/db?query=SELECT * FROM table',
}

example = common_protocols.get(protocol, f"{protocol}://...")
raise AddressResolutionError(
    f"Plugin not found for protocol: {protocol}\n"
    f"  Example usage: {example}\n"
    f"  Available plugins: {', '.join(sorted(p for p in self._plugins.keys() if p.endswith('_')))}"
)
```

**Files to Modify:**
- `src/jn/addressing/resolver.py` (lines 508-511, 459-462, 420-423)

---

### 3. DuckDB Plugin Improvements (Medium Priority)

**Problem:**
DuckDB plugin can fail silently when path or query is missing.

**Current Issues:**
- Silent failures when `--path` is missing
- Not clear what params are supported
- Address parsing could be more robust

**Recommendations:**

```python
# Add validation at the top of reads() function
def reads(config: Optional[dict] = None) -> Iterator[dict]:
    cfg = config or {}

    # ... existing path/query extraction ...

    if not path:
        raise ValueError(
            "DuckDB path is required.\n"
            "  Usage: duckdb://path/to/file.duckdb?query=SELECT * FROM table\n"
            "  Or: jn cat file.duckdb~duckdb?query=SELECT * FROM table"
        )

    if not query:
        raise ValueError(
            "DuckDB query is required.\n"
            "  Usage: duckdb://path/to/file.duckdb?query=SELECT * FROM table\n"
            "  Supported params: query=..., limit=N, param-name=value"
        )
```

**Add docstring with examples:**
```python
def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read from DuckDB database.

    Supported address formats:
        duckdb://path/to/file.duckdb?query=SELECT * FROM users
        duckdb://db.duckdb/table_name          (shorthand for SELECT * FROM table_name)
        file.duckdb~duckdb?query=...           (with format override)

    Supported parameters:
        query=SQL          SQL query to execute
        limit=N            Maximum records to return
        param-name=value   Bind parameters (e.g., param-user_id=123)

    Examples:
        jn cat "duckdb://data.duckdb?query=SELECT * FROM users LIMIT 10"
        jn cat "duckdb://data.duckdb/users?limit=10"
        jn cat "data.duckdb~duckdb?query=SELECT * FROM users WHERE id = $user_id&param-user_id=123"
    """
```

**Files to Modify:**
- User's DuckDB plugin (if copied to jn repo)
- Or: Document best practices in plugin development guide

---

### 4. Parameter Handling Documentation (Medium Priority)

**Problem:**
Not obvious how to pass parameters from address strings to plugins.

**Solution:**
Create comprehensive parameter handling documentation.

**Create:** `docs/parameter-handling.md`

```markdown
# Parameter Handling in JN

## Address Syntax

```
<base>~<format>?<param1>=<value1>&<param2>=<value2>
```

## Parameter Types

### Query String Parameters
Automatically parsed and passed to plugins as config:

```bash
jn cat data.csv?delimiter=;          # delimiter=";"
jn cat data.csv?delimiter=;&header=false   # delimiter=";", header=False
```

### Plugin-Specific Parameters
Each plugin documents supported parameters:

```bash
# CSV plugin
jn cat data.csv?delimiter=TAB&skip_rows=2

# DuckDB plugin
jn cat "duckdb://data.duckdb?query=SELECT * FROM users&limit=100"

# HTTP plugin
jn cat "https://api.com/data?format=json&timeout=30"
```

### Named Bind Parameters (for databases)
Use `param-` prefix for SQL bind parameters:

```bash
jn cat "duckdb://data.duckdb?query=SELECT * FROM users WHERE id = $user_id&param-user_id=123"
```

## Plugin Implementation

Plugins receive parameters via the `config` dict:

```python
def reads(config: Optional[dict] = None) -> Iterator[dict]:
    cfg = config or {}
    delimiter = cfg.get("delimiter", ",")
    skip_rows = cfg.get("skip_rows", 0)
    limit = cfg.get("limit")
    # ...
```

## Type Conversion

The framework automatically converts parameter types:
- `"true"/"false"` → `bool`
- `"123"` → `int`
- `"3.14"` → `float`
- Everything else → `str`

## Error Handling

If a required parameter is missing, raise a clear error:

```python
if not query:
    raise ValueError(
        "query parameter is required\n"
        "  Usage: duckdb://file.duckdb?query=SELECT * FROM table"
    )
```
```

**Files to Create:**
- `docs/parameter-handling.md`
- Update `README.md` with link to parameter docs

---

### 5. Golden Path Examples (High Priority)

**Problem:**
Examples show direct plugin calls instead of using `jn cat | jn filter | jn put`.

**Solution:**
Update all documentation and examples to use the intended architecture.

**Update README.md:**

```markdown
## Quick Start Examples

### ✅ Good: Use jn commands
```bash
# Convert CSV to JSON (CORRECT)
jn cat data.csv | jn put output.json

# Filter with jq (CORRECT)
jn cat data.csv | jn filter '.revenue > 1000' | jn put filtered.csv

# Chain multiple operations (CORRECT)
jn cat https://api.com/users.json | jn filter '.active == true' | jn put active_users.csv
```

### ❌ Bad: Don't call plugins directly
```bash
# DON'T DO THIS - bypasses the framework
python jn_home/plugins/formats/csv_.py --mode read < data.csv

# DON'T DO THIS - loses backpressure and pipeline benefits
python csv_.py --mode read < data.csv | python json_.py --mode write > output.json

# Instead, use:
jn cat data.csv | jn put output.json
```

## Why Use jn Commands?

1. **Automatic backpressure** - OS pipes handle flow control
2. **Memory efficient** - Constant memory usage regardless of file size
3. **Early termination** - `| head -n 10` stops upstream processing
4. **Parallel execution** - Multi-stage pipelines run concurrently
5. **Error handling** - Framework provides better error messages
6. **Plugin discovery** - Framework finds the right plugin automatically
```

**Update CLAUDE.md:**

Add prominent section at the top:

```markdown
## CRITICAL: Always Use JN Commands, Never Call Plugins Directly

**Golden Path:**
```bash
jn cat data.csv | jn filter '.x > 10' | jn put output.json
```

**Anti-Pattern (DON'T DO THIS):**
```bash
python jn_home/plugins/formats/csv_.py --mode read < data.csv  # ❌ WRONG
```

**Why:**
- Direct plugin calls bypass backpressure, early termination, and error handling
- Framework provides better diagnostics and plugin resolution
- Pipeline parallelism only works with proper framework orchestration
```

**Files to Modify:**
- `README.md` (Quick Start section)
- `CLAUDE.md` (add warning at top)
- `docs/` (create `golden-path.md`)
- All example files and tests

---

## Implementation Priority

### P0 (Critical - Do First)
1. ✅ Add `.txt` to CSV plugin matches
2. ✅ Improve error messages in resolver
3. ✅ Add golden path warnings to README/CLAUDE.md

### P1 (High - Do Soon)
4. ⚠️ Create parameter handling documentation
5. ⚠️ Review and improve DuckDB plugin error messages
6. ⚠️ Add more examples using `jn cat | jn filter | jn put`

### P2 (Medium - Do Eventually)
7. 📋 Create plugin development best practices guide
8. 📋 Add validation checks to warn when calling plugins directly
9. 📋 Improve CLI help text with suggestions

---

## Test Cases

After implementing fixes, verify with these test cases:

```bash
# 1. .txt file detection
echo -e "name\tage\nAlice\t30" > test.txt
jn cat test.txt  # Should auto-detect as CSV/TSV

# 2. Better error messages
jn cat unknown.xyz  # Should suggest format override
jn cat "nosuchprotocol://test"  # Should suggest available protocols

# 3. DuckDB plugin
jn cat "duckdb://test.duckdb?query=SELECT * FROM users"  # Should work
jn cat "duckdb://test.duckdb"  # Should give helpful error about missing query

# 4. Parameter handling
jn cat "data.csv?delimiter=;&skip_rows=1"  # Should work
jn cat "data.csv?invalid_param=x"  # Plugin should ignore or warn

# 5. Golden path
jn cat data.csv | jn filter '.age > 25' | jn put output.json  # Should work
```

---

## Summary

The developer feedback highlights real friction points that impact both developer and end-user experience. The recommendations focus on:

1. **Better defaults** - Make common formats (like .txt TSVs) work out of the box
2. **Clearer errors** - Help users fix problems without guessing
3. **Better documentation** - Make parameter handling obvious
4. **Stronger guidance** - Keep users on the golden path

These are all relatively small changes that will have significant impact on usability.

---

## Next Steps

1. Review this evaluation with the JN team
2. Prioritize fixes based on team bandwidth
3. Implement P0 fixes first (should take < 1 hour)
4. Create tracking issues for P1/P2 work
5. Update documentation and examples
6. Validate with original developer who provided feedback

**Estimated Total Effort:** 4-6 hours for all P0+P1 fixes
