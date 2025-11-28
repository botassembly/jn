# Join Command Design

## Problem

Enriching streaming data with related records requires joining datasets. SQL-style joins create row explosions (1-to-many), but for enrichment we want to preserve the primary stream's cardinality while embedding or aggregating matches.

## Design Goals

1. **Stream-friendly** - Left side streams, right side buffered
2. **Cardinality-preserving** - Output one record per input record
3. **Flexible matching** - Key equality, range conditions, or both
4. **Aggregation support** - Compute stats instead of embedding arrays

## Syntax

```bash
jn cat <left> | jn join <right> [options]
```

## Options

| Option | Description |
|--------|-------------|
| `--on <field>` | Natural join - same field name in both sources |
| `--left-key <field>` | Field in left (stdin) records to match on |
| `--right-key <field>` | Field in right source records to match on |
| `--target <field>` | Field name for embedded array of matches |
| `--where <expr>` | Expression to filter matches (e.g., `.line >= .start_line`) |
| `--agg <spec>` | Aggregation spec instead of embedding (e.g., `total: count`) |
| `--inner` | Only emit records with matches (inner join) |
| `--pick <field>` | Fields to include from right records (repeatable) |

## How It Works

```
stdin (left)     right source
    │                 │
    ▼                 ▼
 stream          buffer into
                 hash map
    │                 │
    └────► match ◄────┘
              │
              ▼
         embed/aggregate
              │
              ▼
           stdout
```

**Memory model:** Right side fully buffered, left side streams with constant memory.

## Join Modes

### Natural Join (--on)

Same field name in both sources:

```bash
jn cat customers.csv | jn join orders.csv --on customer_id --target orders
```

### Key Join (--left-key, --right-key)

Different field names:

```bash
jn cat customers.csv | jn join orders.csv \
  --left-key id --right-key customer_id --target orders
```

### Range Join (--where)

Match based on conditions, not just equality:

```bash
jn cat functions.json | jn join coverage.lcov \
  --on file \
  --where ".line >= .start_line and .line <= .end_line" \
  --target lines
```

The `--where` expression has access to both records as `.field` references.

## Aggregation (--agg)

Instead of embedding an array, compute aggregates inline:

```bash
jn cat functions.json | jn join coverage.lcov \
  --on file \
  --where ".line >= .start_line and .line <= .end_line" \
  --agg "total: count, hit: sum(.executed)"
```

### Aggregation Functions

| Function | Description |
|----------|-------------|
| `count` | Number of matches |
| `sum(.field)` | Sum of field values |
| `avg(.field)` | Average of field values |
| `min(.field)` | Minimum value |
| `max(.field)` | Maximum value |

## Output Formats

### Left Join (default)

All left records kept; empty array when no match:

```json
{"id": 1, "name": "Alice", "orders": [{"order_id": "O1"}, {"order_id": "O2"}]}
{"id": 2, "name": "Bob", "orders": []}
```

### Inner Join (--inner)

Only records with matches:

```json
{"id": 1, "name": "Alice", "orders": [{"order_id": "O1"}, {"order_id": "O2"}]}
```

### With Aggregation (--agg)

Aggregates merged into record:

```json
{"id": 1, "name": "Alice", "total": 2, "hit": 1}
```

## Examples

### Customer Orders

```bash
jn cat customers.csv | jn join orders.csv \
  --on customer_id --target orders
```

### Function Coverage

```bash
jn cat "@code/functions?root=src" | jn join coverage.lcov \
  --on file \
  --where ".line >= .start_line and .line <= .end_line" \
  --agg "lines: count, hit: sum(.executed)"
```

### Pick Specific Fields

```bash
jn cat users.csv | jn join profiles.csv \
  --on user_id --target profile \
  --pick email --pick avatar_url
```

## Comparison with jn merge

| Feature | `jn merge` | `jn join` |
|---------|------------|-----------|
| Purpose | Combine streams side-by-side | Enrich with related data |
| Output | Interleaved records | Nested arrays or aggregates |
| Memory | Streaming | Right side buffered |
| Matching | None (concatenation) | Key/range based |

## Location

`src/jn/cli/commands/join.py`
