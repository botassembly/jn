# Join Command: Hash Join for Stream Enrichment

**Status:** Implemented
**Date:** 2025-11-25

---

## Summary

`jn join` enriches a primary NDJSON stream with data from a secondary source based on a shared key. Unlike SQL joins that create row explosions (1-to-many), JN's join **condenses** matches into arrays, preserving the cardinality of the primary stream.

---

## Syntax

```bash
jn cat <left_source> | jn join <right_source> \
  --left-key <field> \
  --right-key <field> \
  --target <new_field_name> \
  [--inner] \
  [--pick <field>...]
```

---

## How It Works

1. **Buffer:** Load right source into memory as a hash map keyed by `--right-key`
2. **Stream:** Read left records from stdin
3. **Enrich:** For each left record, embed matching right records as an array in `--target`

**Memory model:** Right side buffered, left side streams with constant memory.

---

## Options

| Option | Description |
|--------|-------------|
| `--left-key` | Field in left (stdin) records to match on |
| `--right-key` | Field in right source records to match on |
| `--target` | Field name for embedded array of matches |
| `--inner` | Only emit records with matches (inner join) |
| `--pick` | Fields to include from right records (repeatable) |

**Default behavior (left join):** All left records kept; empty array when no match.

---

## Example: Customer Orders

```bash
jn cat customers.csv | jn join orders.csv \
  --left-key id --right-key customer_id --target orders

# Output:
# {"id":"1","name":"Alice","orders":[{"order_id":"O1",...},{"order_id":"O2",...}]}
# {"id":"2","name":"Bob","orders":[]}
```

---

## Example: Dead Code Hunter

Find functions with low coverage and zero callers:

```bash
jn cat coverage.csv | jn join callers.csv \
  --left-key function --right-key callee --target callers \
  | jn filter 'select(.coverage_pct < 10 and (.callers | length) == 0)'
```

---

## Comparison with `jn merge`

| Feature | `jn merge` | `jn join` |
|---------|------------|-----------|
| Purpose | Combine streams side-by-side | Enrich with related data |
| Output | Interleaved records | Nested arrays |
| Memory | Streaming | Right side buffered |
