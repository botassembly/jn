# Join Command: Hash Join for Stream Enrichment

**Status:** Planned
**Date:** 2025-11-25

---

## 1. Executive Summary

JN has excellent tools for fetching data (`jn cat`) and filtering it (`jn filter`), but lacks the ability to **correlate** data from two different sources without writing custom Python scripts. The `jn join` command enables enriching a primary stream with data from a secondary source based on a shared key.

Unlike SQL joins that create row explosions (1-to-many), JN's join **condenses** matches into arrays, preserving the cardinality of the primary stream while embedding related data.

---

## 2. Problem Statement

### Use Case: Dead Code Hunter

We have two distinct streams:
1. **Coverage Data:** Which functions have low execution coverage? (Source: LCOV files)
2. **Reference Data:** Who calls these functions? (Source: Call Graph analysis)

To find dead code, we need to intersect these streams based on the function name:
- Find functions with low coverage
- Enrich with caller information
- Filter for functions with zero callers

### Current Workaround

Today this requires:
1. Run two separate `jn cat` commands
2. Write a Python script to load both
3. Implement the join logic manually

This breaks the composable pipe philosophy of JN.

---

## 3. Challenges & Constraints

### A. Stream Agnosticism
The joiner must operate purely on **NDJSON records**, regardless of origin:
- Left Side: Could be a JSON stream from a REST API
- Right Side: Could be a CSV file on disk or a DuckDB query result

### B. The "1-to-Many" Condensation
In SQL, joining a Function (1) to its Callers (5) creates 5 rows with duplicated function data.

**JN Style:** We want 1 record for the function, containing an **array** of its 5 callers. This preserves the cardinality of the primary stream.

```json
{
  "function": "do_magic",
  "coverage_pct": 5,
  "callers": [
    {"caller": "main"},
    {"caller": "api_handler"}
  ]
}
```

### C. Memory vs. Streaming
To join two streams, you generally have to:
- Hold one side in memory (Hash Join)
- Sort both sides (Merge Join)

**Decision:** Implement a **Hash Join** strategy:
- The "Right" side (enrichment data) is buffered into memory
- The "Left" side (primary stream) remains fully streaming/constant memory

This keeps the interface simple: `jn cat left | jn join right`

---

## 4. The Solution: `jn join`

### Syntax

```bash
jn cat <left_source> | jn join <right_source> \
  --left-key <field> \
  --right-key <field> \
  --target <new_field_name>
```

### How It Works

1. **Phase 1 (Buffering):** `jn join` executes `<right_source>` via `jn cat`. It reads every record and builds an in-memory Hash Map, keyed by `--right-key`.

2. **Phase 2 (Streaming):** It begins reading from `stdin` (the Left Source).

3. **Phase 3 (Enrichment):** For every Left record:
   - Extract the value of `--left-key`
   - Look up matches in the Hash Map
   - Embed the matching records into the Left record under `--target` field
   - Emit the enriched record to `stdout`

---

## 5. Use Cases

### A. Dead Code Hunter

**Left Source (Coverage):**
```json
{"function": "do_magic", "coverage_pct": 5, "file": "utils.c"}
{"function": "unused_helper", "coverage_pct": 0, "file": "legacy.c"}
```

**Right Source (Call Graph):**
```json
{"caller": "main", "callee": "do_magic"}
{"caller": "api_handler", "callee": "do_magic"}
```

**Command:**
```bash
jn cat @lcov/report | \
jn join @graph/references \
  --left-key "function" \
  --right-key "callee" \
  --target "callers"
```

**Output:**
```json
{"function": "do_magic", "coverage_pct": 5, "file": "utils.c", "callers": [{"caller": "main", "callee": "do_magic"}, {"caller": "api_handler", "callee": "do_magic"}]}
{"function": "unused_helper", "coverage_pct": 0, "file": "legacy.c", "callers": []}
```

**Find Dead Code:**
```bash
... | jn filter 'select(.coverage_pct < 10 and (.callers | length) == 0)'
```

### B. Customer Order Enrichment

**Left (Customers):**
```json
{"customer_id": "C001", "name": "Alice", "state": "NY"}
{"customer_id": "C002", "name": "Bob", "state": "CA"}
```

**Right (Orders):**
```json
{"order_id": "O1", "customer_id": "C001", "amount": 100}
{"order_id": "O2", "customer_id": "C001", "amount": 200}
{"order_id": "O3", "customer_id": "C002", "amount": 150}
```

**Command:**
```bash
jn cat customers.csv | \
jn join orders.csv \
  --left-key "customer_id" \
  --right-key "customer_id" \
  --target "orders"
```

**Output:**
```json
{"customer_id": "C001", "name": "Alice", "state": "NY", "orders": [{"order_id": "O1", "customer_id": "C001", "amount": "100"}, {"order_id": "O2", "customer_id": "C001", "amount": "200"}]}
{"customer_id": "C002", "name": "Bob", "state": "CA", "orders": [{"order_id": "O3", "customer_id": "C002", "amount": "150"}]}
```

### C. Unique Customers per State (Aggregation via Join)

**Left (States):**
```json
{"state": "NY"}
{"state": "CA"}
```

**Right (Customers):**
```json
{"customer_id": "C001", "state": "NY"}
{"customer_id": "C002", "state": "CA"}
{"customer_id": "C003", "state": "NY"}
```

**Command:**
```bash
jn cat states.json | \
jn join customers.csv \
  --left-key "state" \
  --right-key "state" \
  --target "customers" \
  --pick "customer_id"
```

**Output:**
```json
{"state": "NY", "customers": [{"customer_id": "C001"}, {"customer_id": "C003"}]}
{"state": "CA", "customers": [{"customer_id": "C002"}]}
```

---

## 6. CLI Options

### Required Options

| Option | Description |
|--------|-------------|
| `<right_source>` | Data source for enrichment (file, URL, profile) |
| `--left-key` | Field name in left records to match on |
| `--right-key` | Field name in right records to match on |
| `--target` | Field name for the embedded array of matches |

### Optional Options

| Option | Default | Description |
|--------|---------|-------------|
| `--inner` | `False` | Only emit records with matches (inner join) |
| `--pick` | (all) | Fields to include from right records (can repeat) |

### Join Modes

**Left Join (Default):**
- Keep all records from the left side
- If no match found, target field is an empty list `[]`
- Perfect for "decorating" data where missing data is information

**Inner Join (`--inner`):**
- Only emit records where a match was found
- Good for filtering: "Show me only customers with orders"

### Field Selection (`--pick`)

Often the right record contains too much data. Use `--pick` to select specific fields:

```bash
jn join orders.csv \
  --left-key customer_id \
  --right-key customer_id \
  --target orders \
  --pick order_id \
  --pick amount
```

Result contains cleaner nested objects with only requested fields.

---

## 7. Implementation

### File: `src/jn/cli/commands/join.py`

```python
"""Join command - enrich stream with data from secondary source."""

import json
import subprocess
import sys
from collections import defaultdict
from typing import Iterator, Optional

import click

from ...context import pass_context
from ...process_utils import popen_with_validation
from ..helpers import build_subprocess_env_for_coverage, check_uv_available


def _load_right_side(
    source: str,
    right_key: str,
    pick_fields: Optional[tuple[str, ...]],
    home_dir=None,
) -> dict[str, list[dict]]:
    """Load right source into a lookup table.

    Returns a dict mapping key values to lists of matching records.
    """
    lookup = defaultdict(list)

    proc = popen_with_validation(
        [sys.executable, "-m", "jn.cli.main", "cat", source],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=build_subprocess_env_for_coverage(home_dir=home_dir),
    )

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        key_value = record.get(right_key)
        if key_value is None:
            continue

        # Convert key to string for consistent matching
        key_str = str(key_value)

        # Apply field selection if specified
        if pick_fields:
            record = {k: record[k] for k in pick_fields if k in record}

        lookup[key_str].append(record)

    proc.wait()
    return dict(lookup)


def _stream_and_enrich(
    lookup: dict[str, list[dict]],
    left_key: str,
    target: str,
    inner_join: bool,
) -> Iterator[dict]:
    """Stream stdin and enrich with lookup data."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        key_value = record.get(left_key)
        key_str = str(key_value) if key_value is not None else None

        matches = lookup.get(key_str, []) if key_str else []

        # Inner join: skip records with no matches
        if inner_join and not matches:
            continue

        # Embed matches into target field
        record[target] = matches
        yield record


@click.command()
@click.argument("right_source")
@click.option(
    "--left-key",
    required=True,
    help="Field in left (stdin) records to match on.",
)
@click.option(
    "--right-key",
    required=True,
    help="Field in right source records to match on.",
)
@click.option(
    "--target",
    required=True,
    help="Field name for embedded array of matches.",
)
@click.option(
    "--inner",
    "inner_join",
    is_flag=True,
    default=False,
    help="Only emit records with matches (inner join).",
)
@click.option(
    "--pick",
    "pick_fields",
    multiple=True,
    help="Fields to include from right records (can repeat).",
)
@pass_context
def join(ctx, right_source, left_key, right_key, target, inner_join, pick_fields):
    """Enrich NDJSON stream with data from a secondary source.

    Reads stdin as the primary (left) stream and enriches each record
    with matching records from the right source, embedded as an array.

    This is a Hash Join: the right source is buffered into memory,
    while the left source streams with constant memory.

    Examples:
        # Enrich customers with their orders
        jn cat customers.csv | jn join orders.csv \\
          --left-key customer_id \\
          --right-key customer_id \\
          --target orders

        # Find functions with their callers
        jn cat coverage.json | jn join callers.json \\
          --left-key function \\
          --right-key callee \\
          --target callers

        # Inner join - only emit matches
        jn cat left.csv | jn join right.csv \\
          --left-key id --right-key id --target matches --inner

        # Pick specific fields from right
        jn cat left.csv | jn join right.csv \\
          --left-key id --right-key id --target data \\
          --pick name --pick value

    Output format:
        {"id": 1, "name": "Alice", "orders": [{"order_id": "O1"}, {"order_id": "O2"}]}
        {"id": 2, "name": "Bob", "orders": []}
    """
    try:
        check_uv_available()

        # Phase 1: Load right side into lookup table
        lookup = _load_right_side(
            right_source,
            right_key,
            pick_fields if pick_fields else None,
            home_dir=ctx.home,
        )

        # Phase 2 & 3: Stream left side and enrich
        for record in _stream_and_enrich(lookup, left_key, target, inner_join):
            print(json.dumps(record), flush=True)

    except KeyboardInterrupt:
        sys.exit(130)
```

### Registration: `src/jn/cli/main.py`

Add to imports:
```python
from .commands.join import join
```

Add to command registration:
```python
cli.add_command(join)
```

---

## 8. Testing Strategy

### Test 1: Basic Left Join

```python
def test_join_basic_left_join(invoke, tmp_path):
    """Test basic left join with matching and non-matching records."""
    left_csv = tmp_path / "customers.csv"
    left_csv.write_text("id,name\n1,Alice\n2,Bob\n3,Charlie\n")

    right_csv = tmp_path / "orders.csv"
    right_csv.write_text("order_id,customer_id,amount\nO1,1,100\nO2,1,200\nO3,2,150\n")

    # Pipe left through stdin
    left_data = invoke(["cat", str(left_csv)])

    result = invoke(
        ["join", str(right_csv),
         "--left-key", "id",
         "--right-key", "customer_id",
         "--target", "orders"],
        input_data=left_data.output
    )

    lines = [json.loads(l) for l in result.output.strip().split("\n") if l]

    alice = next(r for r in lines if r["name"] == "Alice")
    assert len(alice["orders"]) == 2

    bob = next(r for r in lines if r["name"] == "Bob")
    assert len(bob["orders"]) == 1

    charlie = next(r for r in lines if r["name"] == "Charlie")
    assert charlie["orders"] == []  # No matches = empty array
```

### Test 2: Inner Join

```python
def test_join_inner_join(invoke, tmp_path):
    """Test inner join filters out non-matching records."""
    left_csv = tmp_path / "left.csv"
    left_csv.write_text("id,name\n1,Alice\n2,Bob\n")

    right_csv = tmp_path / "right.csv"
    right_csv.write_text("id,value\n1,100\n")  # Only matches id=1

    left_data = invoke(["cat", str(left_csv)])

    result = invoke(
        ["join", str(right_csv),
         "--left-key", "id",
         "--right-key", "id",
         "--target", "data",
         "--inner"],
        input_data=left_data.output
    )

    lines = [json.loads(l) for l in result.output.strip().split("\n") if l]

    assert len(lines) == 1
    assert lines[0]["name"] == "Alice"
```

### Test 3: Pick Fields

```python
def test_join_pick_fields(invoke, tmp_path):
    """Test --pick option filters right record fields."""
    left_csv = tmp_path / "left.csv"
    left_csv.write_text("id,name\n1,Alice\n")

    right_csv = tmp_path / "right.csv"
    right_csv.write_text("id,value,extra,noise\n1,100,A,X\n")

    left_data = invoke(["cat", str(left_csv)])

    result = invoke(
        ["join", str(right_csv),
         "--left-key", "id",
         "--right-key", "id",
         "--target", "data",
         "--pick", "value",
         "--pick", "extra"],
        input_data=left_data.output
    )

    lines = [json.loads(l) for l in result.output.strip().split("\n") if l]
    record = lines[0]

    assert "data" in record
    assert len(record["data"]) == 1
    assert record["data"][0] == {"value": "100", "extra": "A"}
    assert "noise" not in record["data"][0]
```

---

## 9. Memory Considerations

The right side is fully buffered in memory. For very large right sources, consider:
- Filtering the right source before joining
- Using database pushdown (`jn cat @db/query?limit=N`)
- Implementing a disk-backed lookup in a future version

Typical use cases (enrichment data < 1M records) will work fine with in-memory lookup.

---

## 10. Comparison with `jn merge`

| Feature | `jn merge` | `jn join` |
|---------|------------|-----------|
| Purpose | Combine multiple streams | Enrich stream with related data |
| Output | Interleaved records with metadata | Single enriched records with nested arrays |
| Memory | Streaming (constant) | Right side buffered |
| Use Case | Comparative analysis | Data correlation/enrichment |

---

## 11. File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `src/jn/cli/commands/join.py` | **New** | Join command implementation |
| `src/jn/cli/main.py` | Modify | Register join command |
| `tests/cli/test_join.py` | **New** | Join command tests |
| `CLAUDE.md` | Modify | Document join command |

---

## 12. Future Enhancements

1. **Disk-backed lookup** - For very large right sources
2. **Multi-key join** - Join on composite keys
3. **Right join mode** - Emit all right records
4. **Full outer join** - Emit all records from both sides
5. **Streaming merge join** - For pre-sorted data
