# Joining and Multi-Source Operations

> **Purpose**: How to combine data from multiple sources.

---

## The Join Problem

Data often needs to be correlated across sources:
- Orders need customer details
- Log entries need user information
- Metrics need dimension labels

JN provides two approaches:
- **Join**: Correlate records by key
- **Merge**: Concatenate multiple sources

---

## `jn join` - Hash Join

Joins data from stdin with another source using hash-based matching.

### Basic Usage

```bash
# Enrich orders with customer data
jn cat orders.csv | jn join customers.csv --on customer_id
```

Input (orders.csv):
```json
{"order_id": "O1", "customer_id": "C1", "amount": 100}
{"order_id": "O2", "customer_id": "C2", "amount": 200}
```

Right source (customers.csv):
```json
{"customer_id": "C1", "name": "Alice", "region": "West"}
{"customer_id": "C2", "name": "Bob", "region": "East"}
```

Output:
```json
{"order_id": "O1", "customer_id": "C1", "amount": 100, "name": "Alice", "region": "West"}
{"order_id": "O2", "customer_id": "C2", "amount": 200, "name": "Bob", "region": "East"}
```

### Architecture

Join uses a hash-based algorithm:

```
Right Source              Left Source (stdin)
     │                          │
     ▼                          │
┌──────────┐                    │
│  Load    │                    │
│  into    │                    │
│ hash map │                    │
└──────────┘                    │
     │                          ▼
     │                    ┌──────────┐
     │                    │  Stream  │
     └──────────────────▶ │  lookup  │ ─────▶ Output
                          │  & merge │
                          └──────────┘
```

**Key insight**: Right source is buffered, left source streams.

Put the smaller dataset on the right for memory efficiency.

---

## Join Key Modes

### Natural Join

Same field name on both sides:

```bash
jn cat orders.csv | jn join customers.csv --on customer_id
```

Both datasets must have `customer_id` field.

### Named Join

Different field names:

```bash
jn cat orders.csv | jn join customers.csv \
  --left-key cust_id \
  --right-key id
```

Maps `orders.cust_id` to `customers.id`.

### Composite Keys

Multiple fields form the key:

```bash
jn cat transactions.csv | jn join accounts.csv \
  --on "bank_code,account_number"
```

Matches when both fields match.

---

## Join Types

### Left Join (Default)

All left records, with right data if matched:

```bash
jn cat orders.csv | jn join customers.csv --on customer_id
```

Unmatched orders have `null` for customer fields.

### Inner Join

Only records with matches on both sides:

```bash
jn cat orders.csv | jn join customers.csv --on customer_id --inner
```

Orders without matching customers are excluded.

### Left Outer with Indicator

Add field showing match status:

```bash
jn cat orders.csv | jn join customers.csv --on customer_id --indicator=matched
```

Output includes `"matched": true` or `"matched": false`.

---

## Output Modes

### Flat Merge (Default)

Right fields merged into left record:

```json
{"order_id": "O1", "customer_id": "C1", "amount": 100, "name": "Alice"}
```

Field conflicts: Right values overwrite left.

### Embed as Array

Matches embedded in a field:

```bash
jn cat customers.csv | jn join orders.csv --on customer_id --target orders
```

Output:
```json
{
  "customer_id": "C1",
  "name": "Alice",
  "orders": [
    {"order_id": "O1", "amount": 100},
    {"order_id": "O2", "amount": 150}
  ]
}
```

Useful for one-to-many relationships.

### Pick Fields

Select specific fields from right:

```bash
jn cat orders.csv | jn join customers.csv --on customer_id \
  --pick name,region
```

Only includes `name` and `region` from customers.

### Prefix Fields

Avoid conflicts with prefixes:

```bash
jn cat orders.csv | jn join customers.csv --on customer_id \
  --prefix customer_
```

Right fields become `customer_name`, `customer_region`.

---

## Aggregation

Compute aggregates over matches:

```bash
jn cat customers.csv | jn join orders.csv --on customer_id \
  --agg "order_count: count(), total: sum(.amount), avg_order: avg(.amount)"
```

Output:
```json
{
  "customer_id": "C1",
  "name": "Alice",
  "order_count": 3,
  "total": 450,
  "avg_order": 150
}
```

### Available Aggregations

| Function | Description |
|----------|-------------|
| `count()` | Number of matches |
| `sum(.field)` | Sum of numeric field |
| `avg(.field)` | Average of numeric field |
| `min(.field)` | Minimum value |
| `max(.field)` | Maximum value |
| `first(.field)` | First matched value |
| `last(.field)` | Last matched value |
| `collect(.field)` | Array of all values |

---

## Condition Joins

Join on conditions beyond equality:

```bash
jn cat log_entries.csv | jn join time_ranges.csv \
  --where ".timestamp >= .start_time and .timestamp < .end_time"
```

### Expression Syntax

- `.field`: Field from left record
- `$.field`: Field from right record
- Operators: `==`, `!=`, `<`, `<=`, `>`, `>=`, `and`, `or`

### Range Join Example

Match log entries to time windows:

```bash
jn cat logs.csv | jn join shifts.csv \
  --where ".timestamp >= $.shift_start and .timestamp < $.shift_end"
```

Note: Condition joins may be slower (no hash optimization).

---

## `jn merge` - Concatenate Sources

Combines multiple sources into a single stream.

### Basic Usage

```bash
jn merge jan.csv feb.csv mar.csv | jn put q1.csv
```

Records from all sources concatenated in order.

### Source Tagging

Add source information to each record:

```bash
jn merge jan.csv feb.csv mar.csv
```

Output:
```json
{"_source": "jan.csv", "date": "2024-01-15", "amount": 100}
{"_source": "jan.csv", "date": "2024-01-20", "amount": 200}
{"_source": "feb.csv", "date": "2024-02-10", "amount": 150}
```

### Custom Labels

Provide meaningful labels:

```bash
jn merge "jan.csv:label=January" "feb.csv:label=February"
```

Output:
```json
{"_source": "jan.csv", "_label": "January", "date": "2024-01-15", "amount": 100}
```

### Mixed Sources

Combine files, URLs, and profiles:

```bash
jn merge local.csv @api/remote "https://example.com/data.json"
```

Each source can be any valid address.

---

## Error Handling

### Join Errors

| Scenario | Behavior |
|----------|----------|
| Right source fails to load | Error, abort |
| Left record missing key | Skip record, warn |
| Type mismatch in key | Coerce to string |

### Merge Errors

| Mode | Behavior |
|------|----------|
| Fail-fast | Stop on first source error |
| Fail-safe (default) | Skip failed sources, continue |

```bash
# Stop on first error
jn merge --fail-fast source1.csv source2.csv

# Continue despite errors
jn merge source1.csv source2.csv  # default behavior
```

---

## Memory Considerations

### Join Memory

Right source is fully loaded:

| Right Size | Memory Usage |
|------------|--------------|
| 1 MB | ~5 MB |
| 100 MB | ~500 MB |
| 1 GB | ~5 GB |

**Rule**: Put smaller dataset on right.

### Merge Memory

Merge streams sources sequentially:

```
Source 1 ─────────▶ ─────────▶ ─────────▶
                    Source 2 ─────────▶ ─────────▶
                                        Source 3 ─────────▶
```

Memory: O(buffer), regardless of total data.

### Large Join Strategies

For very large right sources:

1. **Filter first**: Reduce right source before join
2. **Partition**: Split into multiple smaller joins
3. **Use database**: Load into DuckDB, use SQL join

```bash
# Filter right source
jn cat customers.csv | jn filter '.active' > active_customers.csv
jn cat orders.csv | jn join active_customers.csv --on customer_id
```

---

## Use Cases

### Enrichment

Add context from lookup table:

```bash
jn cat transactions.csv | jn join products.csv --on product_id \
  --pick product_name,category
```

### Aggregation Report

Summarize by dimension:

```bash
jn cat orders.csv | jn join customers.csv --on customer_id \
  --agg "total_orders: count(), revenue: sum(.amount)" \
  | jn put customer_summary.csv
```

### Multi-Source Consolidation

Combine data from different systems:

```bash
jn merge @crm/customers @billing/accounts @support/tickets \
  | jn filter '.customer_id == "C123"' \
  | jn put customer_360.json
```

### Time-Based Correlation

Match events to time windows:

```bash
jn cat events.csv | jn join campaigns.csv \
  --where ".timestamp >= $.start_date and .timestamp <= $.end_date" \
  | jn put attributed_events.csv
```

---

## Design Decisions

### Why Hash Join?

**Benefits**:
- O(1) lookup per left record
- Streaming left side
- Simple implementation

**Trade-offs**:
- Right side must fit in memory
- Condition joins fall back to nested loop

### Why Stream Left, Buffer Right?

```
Left (stream)  →  Hash Table (buffer)  →  Output
    ↑                    ↑
  large               small
```

Most use cases have a large transaction table joined with a small dimension table. Streaming the large side keeps memory bounded.

### Why Merge is Sequential?

Parallel merging would require:
- Coordination overhead
- Order unpredictability
- Complex buffering

Sequential is simpler and order is predictable.

---

## See Also

- [03-users-guide.md](03-users-guide.md) - Join and merge examples
- [08-streaming-backpressure.md](08-streaming-backpressure.md) - Memory characteristics
- [02-architecture.md](02-architecture.md) - Multi-source pipeline
