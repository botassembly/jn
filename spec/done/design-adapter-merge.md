# Adapter Pattern & Merge: Unified Data Orchestration

**Status:** ✅ Implemented
**Date:** 2025-11-25

---

## 1. Executive Summary

JN is not just a pipe tool; it is an **Orchestration Engine**. Use cases like cohort comparison or daily sales analysis should be defined declaratively within JN profiles, not scattered across shell scripts.

To achieve this, we are unifying data access under the **Adapter Pattern**:
1. **Pushdown Adapters (SQL):** Transform data *at the source* (database)
2. **Streaming Adapters (JQ):** Transform data *in the pipe* (files/APIs)
3. **Composability (Merge):** Combine multiple adapted streams into a unified flow

---

## 2. Feature: Parameterized SQL Adapters with Optional Filters

### The Problem

Users currently create static SQL files for every permutation of a query (`folfox.sql`, `folfiri.sql`). This creates maintenance debt and prevents dynamic analysis.

### Current State

The DuckDB plugin **already supports** parameterized queries with `$param` syntax:
```sql
SELECT * FROM users WHERE id = $user_id
```

Invoked as:
```bash
jn cat "@analytics/by-user?user_id=123"
```

**What's missing:** The ability to have **optional parameters** that are ignored when not provided.

### The Solution: Optional Filter Pattern

Use SQL's NULL-check pattern to make parameters optional:

```sql
-- profiles/duckdb/genie/treatment.sql
-- Master treatment query with optional filters
-- Parameters: regimen, min_survival

SELECT
    patient_id,
    regimen,
    os_months
FROM treatments
WHERE
    ($regimen IS NULL OR regimen = $regimen)
    AND
    ($min_survival IS NULL OR os_months >= $min_survival)
```

**Usage:**
```bash
# Get everything (params default to NULL)
jn cat "@genie/treatment"

# Get specific regimen
jn cat "@genie/treatment?regimen=FOLFOX"

# Get high survivors on specific regimen
jn cat "@genie/treatment?regimen=FOLFIRI&min_survival=12"
```

### Implementation Requirements

1. **NULL Parameter Binding:** Missing CLI parameters must pass as `NULL` to the database, not be omitted from the parameter dict
2. **Parameter Discovery:** Extract declared parameters from `-- Parameters:` comment
3. **Auto-NULL Injection:** For any declared parameter not provided, inject `NULL`

### Changes Required

**File:** `jn_home/plugins/databases/duckdb_.py`

```python
def reads(config: Optional[dict] = None) -> Iterator[dict]:
    # ... existing code ...

    # NEW: Extract declared parameters from SQL comments
    declared_params = _extract_declared_params(sql_content)

    # NEW: Inject NULL for missing declared parameters
    for param in declared_params:
        if param not in params:
            params[param] = None

    # Execute with parameters (including NULLs)
    cursor = conn.execute(query, params or None)
```

---

## 3. Feature: Parameterized JQ Adapters

### The Problem

Users dealing with flat files (CSVs, Excel, JSON APIs) often need different "views" of the same source. Writing raw JQ strings in the terminal is error-prone and hard to reuse.

### Current State

JQ profiles exist and support parameter substitution via string replacement:
```jq
# profiles/jq/builtin/group_count.jq
# Parameters: by
group_by(.[$by]) | ...
```

The framework replaces `$by` with `"status"` before passing to jq.

**Limitations:**
- String substitution is error-prone (no type safety)
- Can't use jq's native `--arg` mechanism
- Complex expressions with `$` get confused

### The Solution: Native JQ Argument Binding

Extend the jq plugin to use jq's native `--arg` mechanism:

**Profile:** `profiles/jq/sales/by_region.jq`
```jq
# Description: Filter and transform sales by region
# Parameters: region, threshold

select(.Region == $region)
| select((.Amount | tonumber) > ($threshold | tonumber))
| {
    date: .Date,
    item: .Item,
    amount: .Amount,
    sales_rep: .Rep
}
```

**Execution:**
```bash
# Via profile with adapter syntax
jn cat data.csv | jn filter "@sales/by_region?region=East&threshold=1000"
```

### Implementation Requirements

1. **Argument Injection:** Build `--arg` flags from parameters
2. **Profile as File:** Pass `.jq` file path to jq instead of inlined content
3. **Backward Compatibility:** Continue supporting simple string substitution

### Changes Required

**File:** `jn_home/plugins/filters/jq_.py`

```python
#!/usr/bin/env -S uv run --script
import subprocess
import sys
import json

if __name__ == "__main__":
    # Parse arguments
    # New format: jq_.py <query_or_path> [--jq-arg key value ...]

    args = sys.argv[1:]
    query = args[0] if args else "."
    jq_args = []

    # Build --arg flags
    i = 1
    while i < len(args):
        if args[i] == "--jq-arg" and i + 2 < len(args):
            jq_args.extend(["--arg", args[i+1], args[i+2]])
            i += 3
        else:
            i += 1

    # If query is a file path, use -f flag
    if query.endswith(".jq"):
        cmd = ["jq", "-c"] + jq_args + ["-f", query]
    else:
        cmd = ["jq", "-c"] + jq_args + [query]

    proc = subprocess.Popen(cmd, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    sys.exit(proc.wait())
```

**File:** `src/jn/cli/commands/filter.py`

```python
# When resolving profile, return both content AND params
if is_profile_reference(query):
    profile_path, params = resolve_jq_profile_with_args(query)

    # Build jq-arg flags
    jq_arg_flags = []
    for key, value in params.items():
        jq_arg_flags.extend(["--jq-arg", key, value])

    cmd = ["uv", "run", "--script", plugin.path, profile_path] + jq_arg_flags
```

---

## 4. Feature: `jn merge` Command

### The Problem

To compare two datasets (e.g., "East Sales vs West Sales"), users currently:
1. Run two separate commands
2. Output to temp files
3. Write a script to load both

This breaks the flow and doesn't leverage JN's streaming architecture.

### The Solution

A native `merge` command that executes multiple sources and interleaves them into a single stream with metadata injection.

### Syntax

```bash
jn merge \
  "source1:label=Label1" \
  "source2:label=Label2" \
  [--mode sequential|interleave]
```

### Use Case: Comparative Analysis

```bash
jn merge \
  "@sales/daily?adapter=by_region&region=East:label=EastCoast" \
  "@sales/daily?adapter=by_region&region=West:label=WestCoast" \
  | jn view
```

**Output Stream (NDJSON):**
```json
{"date": "2024-01-15", "amount": 500, "_label": "EastCoast", "_source": "@sales/daily?..."}
{"date": "2024-01-15", "amount": 450, "_label": "WestCoast", "_source": "@sales/daily?..."}
{"date": "2024-01-16", "amount": 1200, "_label": "EastCoast", "_source": "@sales/daily?..."}
```

### Implementation

**File:** `src/jn/cli/commands/merge.py`

```python
@click.command()
@click.argument("sources", nargs=-1, required=True)
@click.option("--mode", type=click.Choice(["sequential", "interleave"]), default="sequential")
@pass_context
def merge(ctx, sources, mode):
    """Merge multiple data sources into a single NDJSON stream.

    Each source can have a label suffix: source:label=MyLabel

    Examples:
        # Compare two CSV files
        jn merge "east.csv:label=East" "west.csv:label=West"

        # Compare profile queries
        jn merge "@sales/q1:label=Q1" "@sales/q2:label=Q2"

        # Merge API endpoints
        jn merge "http://api/users" "http://api/admins:label=Admin"
    """
    for source_spec in sources:
        source, label = _parse_source_spec(source_spec)

        # Execute source via jn cat
        proc = popen_with_validation(
            [sys.executable, "-m", "jn.cli.main", "cat", source],
            stdout=PIPE,
            text=True
        )

        # Inject metadata into each record
        for line in proc.stdout:
            record = json.loads(line)
            record["_label"] = label
            record["_source"] = source
            print(json.dumps(record), flush=True)

        proc.wait()


def _parse_source_spec(spec: str) -> tuple[str, str]:
    """Parse 'source:label=Label' into (source, label)."""
    if ":label=" in spec:
        source, label_part = spec.rsplit(":label=", 1)
        return source, label_part
    return spec, spec  # Use source as default label
```

### CLI Registration

**File:** `src/jn/cli/main.py`

```python
from .commands.merge import merge
cli.add_command(merge)
```

---

## 5. Adapter Resolution Flow

### Current Flow (Profile References)

```
@namespace/query?param=value
         ↓
AddressResolver → Find plugin (duckdb_, http_, etc.)
         ↓
Plugin executes with parameters
```

### New Flow (Adapter References)

```
@source/name?adapter=filter_name&filter_param=value
         ↓
1. Parse: source=@source/name, adapter=filter_name, params={filter_param: value}
         ↓
2. Execute source: jn cat @source/name
         ↓
3. Pipe through adapter: jn filter @source/filter_name?filter_param=value
         ↓
Output stream
```

### Implementation Notes

The `adapter=` parameter is special:
- Extracted from query params before passing to source
- Used to locate a JQ profile in the same namespace as the source
- Applied as a post-processing filter

---

## 6. Testing Strategy

### Test 1: SQL Optional Parameters

```python
def test_duckdb_optional_params(invoke, tmp_path):
    """Test optional parameter pattern with NULL defaults."""
    # Create test DB with sample data
    db_path = tmp_path / "test.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("CREATE TABLE users (id INT, name VARCHAR, status VARCHAR)")
    conn.execute("INSERT INTO users VALUES (1, 'Alice', 'active')")
    conn.execute("INSERT INTO users VALUES (2, 'Bob', 'inactive')")
    conn.close()

    # Create profile with optional filter
    profile_dir = tmp_path / "profiles" / "duckdb" / "test"
    profile_dir.mkdir(parents=True)

    (profile_dir / "_meta.json").write_text(json.dumps({"path": str(db_path)}))
    (profile_dir / "users.sql").write_text("""
-- Users with optional status filter
-- Parameters: status
SELECT * FROM users WHERE ($status IS NULL OR status = $status)
""")

    # Test 1: No params - should return all
    result = invoke(["cat", "@test/users"], env={"JN_HOME": str(tmp_path)})
    assert len(result.output.strip().split("\n")) == 2

    # Test 2: With status param - should filter
    result = invoke(["cat", "@test/users?status=active"], env={"JN_HOME": str(tmp_path)})
    assert len(result.output.strip().split("\n")) == 1
    assert "Alice" in result.output
```

### Test 2: JQ Native Arguments

```python
def test_jq_native_args(invoke, tmp_path):
    """Test jq --arg parameter passing."""
    # Create test JQ profile
    profile_dir = tmp_path / "profiles" / "jq" / "test"
    profile_dir.mkdir(parents=True)

    (profile_dir / "filter_by.jq").write_text("""
# Filter by field value
# Parameters: field, value
select(.[$field] == $value)
""")

    # Create test data
    data = '[{"name": "Alice", "city": "NYC"}, {"name": "Bob", "city": "LA"}]'

    # Test: Filter by city
    result = invoke(
        ["filter", "@test/filter_by?field=city&value=NYC"],
        input=data,
        env={"JN_HOME": str(tmp_path)}
    )
    assert "Alice" in result.output
    assert "Bob" not in result.output
```

### Test 3: Merge with Labels

```python
def test_merge_labels(invoke, tmp_path):
    """Test merge command with label injection."""
    # Create two CSV files
    (tmp_path / "east.csv").write_text("id,value\n1,100\n")
    (tmp_path / "west.csv").write_text("id,value\n2,200\n")

    result = invoke([
        "merge",
        f"{tmp_path}/east.csv:label=East",
        f"{tmp_path}/west.csv:label=West"
    ])

    lines = result.output.strip().split("\n")
    assert len(lines) == 2

    record1 = json.loads(lines[0])
    assert record1["_label"] == "East"
    assert record1["id"] == "1"

    record2 = json.loads(lines[1])
    assert record2["_label"] == "West"
    assert record2["id"] == "2"
```

---

## 7. Demo Plan

Create `demos/adapter-merge/` with:

1. **demo-sql-optional.sh** - Clinical cohort analysis with optional filters
2. **demo-jq-adapter.sh** - Sales data transformation with JQ adapters
3. **demo-merge-compare.sh** - Side-by-side regional comparison

---

## 8. File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `jn_home/plugins/databases/duckdb_.py` | Modify | Add NULL injection for optional params |
| `jn_home/plugins/filters/jq_.py` | Modify | Add --arg support, file input mode |
| `src/jn/cli/commands/filter.py` | Modify | Pass params as --jq-arg flags |
| `src/jn/cli/commands/merge.py` | **New** | Merge command implementation |
| `src/jn/cli/main.py` | Modify | Register merge command |
| `tests/cli/test_duckdb.py` | Modify | Add optional param tests |
| `tests/cli/test_jq_profiles.py` | Modify | Add native arg tests |
| `tests/cli/test_merge.py` | **New** | Merge command tests |

---

## 9. Migration Notes

### Backward Compatibility

All existing functionality remains unchanged:
- Existing DuckDB profiles work (no changes to required params)
- Existing JQ profiles work (string substitution still supported)
- No breaking changes to CLI syntax

### Upgrade Path

1. **SQL profiles:** Add optional params by using `($param IS NULL OR column = $param)` pattern
2. **JQ profiles:** No changes needed; native args are opt-in improvement
3. **Workflows:** Use `jn merge` instead of shell scripts for comparisons
