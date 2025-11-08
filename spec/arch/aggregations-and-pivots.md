# Aggregations and Pivot Tables

## Overview

Use jq for aggregations, grouping, and pivot table operations. JN doesn't need a custom DSL - jq already provides powerful grouping and aggregation primitives.

## Philosophy

**No custom DSL needed**: jq's `group_by`, `map`, and built-in aggregation functions (`add`, `max`, `min`, `length`) handle 99% of use cases.

**Provide patterns, not syntax**: Document common patterns users can copy and adapt. Advanced users can write custom jq for complex scenarios.

## Core jq Pattern for Aggregations

### The Pattern

```jq
group_by(.field) | map({
  field: .[0].field,
  count: length,
  total: map(.value) | add,
  avg: (map(.value) | add) / length,
  max: map(.value) | max,
  min: map(.value) | min
})
```

### How It Works

1. **`group_by(.field)`** - Groups records by field value into arrays
2. **`map(...)`** - Transform each group into aggregated result
3. **`.[0].field`** - Get field value from first record in group
4. **`length`** - Count records in group
5. **`map(.value) | add`** - Sum all values
6. **`map(.value) | max/min`** - Get max/min value

## Common Aggregation Examples

### Example Data

```json
{"date": "2025-01-15", "category": "Electronics", "amount": 1200, "quantity": 2}
{"date": "2025-01-15", "category": "Books", "amount": 45, "quantity": 3}
{"date": "2025-01-15", "category": "Electronics", "amount": 800, "quantity": 1}
{"date": "2025-01-16", "category": "Electronics", "amount": 1500, "quantity": 2}
{"date": "2025-01-16", "category": "Books", "amount": 60, "quantity": 4}
```

### 1. Group By Single Field (COUNT)

**SQL equivalent**: `SELECT category, COUNT(*) FROM sales GROUP BY category`

```bash
jn cat sales.csv | jq -s 'group_by(.category) | map({
  category: .[0].category,
  count: length
})'
```

**Output**:
```json
[
  {"category": "Books", "count": 2},
  {"category": "Electronics", "count": 3}
]
```

### 2. Group By with SUM

**SQL equivalent**: `SELECT category, SUM(amount) FROM sales GROUP BY category`

```bash
jn cat sales.csv | jq -s 'group_by(.category) | map({
  category: .[0].category,
  total: map(.amount) | add
})'
```

**Output**:
```json
[
  {"category": "Books", "total": 105},
  {"category": "Electronics", "total": 3500}
]
```

### 3. Multiple Aggregations

**SQL equivalent**: `SELECT category, COUNT(*), SUM(amount), AVG(amount), MAX(amount) FROM sales GROUP BY category`

```bash
jn cat sales.csv | jq -s 'group_by(.category) | map({
  category: .[0].category,
  count: length,
  total: map(.amount) | add,
  avg: (map(.amount) | add) / length,
  max: map(.amount) | max,
  min: map(.amount) | min
})'
```

**Output**:
```json
[
  {
    "category": "Books",
    "count": 2,
    "total": 105,
    "avg": 52.5,
    "max": 60,
    "min": 45
  },
  {
    "category": "Electronics",
    "count": 3,
    "total": 3500,
    "avg": 1166.67,
    "max": 1500,
    "min": 800
  }
]
```

### 4. Group By Multiple Fields

**SQL equivalent**: `SELECT date, category, SUM(amount) FROM sales GROUP BY date, category`

```bash
jn cat sales.csv | jq -s 'group_by([.date, .category]) | map({
  date: .[0].date,
  category: .[0].category,
  total: map(.amount) | add
})'
```

**Output**:
```json
[
  {"date": "2025-01-15", "category": "Books", "total": 45},
  {"date": "2025-01-15", "category": "Electronics", "total": 2000},
  {"date": "2025-01-16", "category": "Books", "total": 60},
  {"date": "2025-01-16", "category": "Electronics", "total": 1500}
]
```

### 5. Pivot Table (Category × Date)

**SQL equivalent**: Complex pivot query with CASE statements

```bash
jn cat sales.csv | jq -s '
  group_by(.category) | map({
    category: .[0].category,
    "2025-01-15": map(select(.date == "2025-01-15") | .amount) | add // 0,
    "2025-01-16": map(select(.date == "2025-01-16") | .amount) | add // 0
  })
'
```

**Output**:
```json
[
  {"category": "Books", "2025-01-15": 45, "2025-01-16": 60},
  {"category": "Electronics", "2025-01-15": 2000, "2025-01-16": 1500}
]
```

### 6. Dynamic Pivot (Auto-Detect Date Columns)

```bash
jn cat sales.csv | jq -s '
  (map(.date) | unique) as $dates |
  group_by(.category) | map(
    {category: .[0].category} +
    ($dates | map(. as $d | {($d): (map(select(.date == $d) | .amount) | add // 0)}) | add)
  )
'
```

**Output**: Same as above, but dates are auto-detected from data.

### 7. Percentages (Group Totals)

**SQL equivalent**: `SELECT category, amount, amount / SUM(amount) OVER (PARTITION BY category) as pct FROM sales`

```bash
jn cat sales.csv | jq -s '
  group_by(.category) | map(
    map(.amount) | add as $total |
    map(. + {pct: (.amount / $total * 100)})
  ) | flatten
'
```

### 8. Running Totals

```bash
jn cat sales.csv | jq -s 'sort_by(.date) |
  reduce .[] as $item (
    {items: [], total: 0};
    .total += $item.amount |
    .items += [$item + {running_total: .total}]
  ) | .items
'
```

### 9. Top N per Group

**Get top 2 sales per category**:

```bash
jn cat sales.csv | jq -s '
  group_by(.category) | map(
    {category: .[0].category, top_sales: (sort_by(.amount) | reverse | .[0:2])}
  )
'
```

### 10. Histogram (Binning)

**Count sales by amount ranges**:

```bash
jn cat sales.csv | jq -s 'map(
  if .amount < 100 then .bin = "0-100"
  elif .amount < 500 then .bin = "100-500"
  elif .amount < 1000 then .bin = "500-1000"
  else .bin = "1000+"
  end
) | group_by(.bin) | map({range: .[0].bin, count: length})'
```

## Advanced Patterns

### Custom Aggregation Functions

```bash
# Median
jn cat data.csv | jq -s 'group_by(.category) | map({
  category: .[0].category,
  median: (map(.amount) | sort | if length % 2 == 0 then (.[length/2 - 1] + .[length/2]) / 2 else .[length/2 | floor] end)
})'

# Standard deviation
jn cat data.csv | jq -s 'group_by(.category) | map(
  map(.amount) | add / length as $mean |
  {
    category: .[0].category,
    stddev: (map(pow(. - $mean; 2)) | add / length | sqrt)
  }
)'
```

### Cross-Tabulation (Two-Way Pivot)

**Category × Date with multiple metrics**:

```bash
jn cat sales.csv | jq -s '
  (map(.date) | unique) as $dates |
  group_by(.category) | map(
    {category: .[0].category} +
    ($dates | map(
      . as $d |
      {
        ($d + "_total"): (map(select(.date == $d) | .amount) | add // 0),
        ($d + "_count"): (map(select(.date == $d)) | length)
      }
    ) | add)
  )
'
```

## Use Cases with JN

### Example 1: Sales Report from CSV

```bash
# Daily sales summary
jn cat sales.csv | jq -s 'group_by(.date) | map({
  date: .[0].date,
  total_sales: map(.amount) | add,
  transaction_count: length,
  avg_transaction: (map(.amount) | add) / length
})' | jn put daily-summary.xlsx
```

### Example 2: API Data Aggregation

```bash
# Aggregate API events by user and action
jn cat https://api.example.com/events | jq -s 'group_by([.user_id, .action]) | map({
  user_id: .[0].user_id,
  action: .[0].action,
  count: length,
  first_seen: map(.timestamp) | min,
  last_seen: map(.timestamp) | max
})' | jn put user-actions.json
```

### Example 3: Log Analysis

```bash
# Analyze error logs by hour
jn cat access.log --parser apache_log_s | jq -s 'map(
  .timestamp | split(":")[1] as $hour |
  . + {hour: $hour}
) | group_by(.hour) | map({
  hour: .[0].hour,
  requests: length,
  errors: map(select(.status >= 400)) | length,
  error_rate: (map(select(.status >= 400)) | length) / length * 100
})' | jn put hourly-stats.json
```

### Example 4: Multi-Sheet Excel Report

```bash
# Generate multi-sheet report with aggregations
jn cat transactions.csv | jq -s '
  [
    (group_by(.category) | map({
      sheet: "By Category",
      category: .[0].category,
      total: map(.amount) | add
    })),
    (group_by(.date) | map({
      sheet: "By Date",
      date: .[0].date,
      total: map(.amount) | add
    }))
  ] | flatten
' | jn put report.xlsx --multi-sheet
```

## When NOT to Use jq

### Use SQL Instead

For very large datasets (>1GB), use a database:

```bash
# Load to SQLite first
jn cat large-data.csv | sqlite3 data.db '.import /dev/stdin sales'

# Then query
sqlite3 data.db "SELECT category, SUM(amount) FROM sales GROUP BY category" | \
  jn cat - --parser csv
```

### Use pandas/Python for Complex Stats

For statistical analysis (regression, correlation, ML):

```python
import pandas as pd
import json

# Read NDJSON from JN
df = pd.read_json('sales.json', lines=True)

# Complex aggregation
result = df.groupby('category').agg({
    'amount': ['sum', 'mean', 'std'],
    'quantity': 'sum'
}).reset_index()

# Back to NDJSON
result.to_json('aggregated.json', orient='records', lines=True)
```

## Should We Add a DSL?

### Arguments Against

1. **jq is already powerful** - Can express any aggregation
2. **Users need to learn jq anyway** - For converters, filtering
3. **DSL adds complexity** - Parser, validator, jq code generator
4. **Limited flexibility** - DSL can't cover all edge cases
5. **Maintenance burden** - Two languages to maintain

### Arguments For

1. **Easier for non-programmers** - SQL-like syntax is familiar
2. **Fewer errors** - Validated structure vs manual jq
3. **Discoverability** - Clear what operations are available

### Recommendation: Start Without DSL

**Phase 1**: Document jq patterns (this document)
**Phase 2**: If users struggle, add optional SQL-like aggregation syntax
**Phase 3**: Compile SQL-like syntax to jq internally

**Example future syntax** (if needed):
```bash
jn cat sales.csv --aggregate "
  SELECT category,
         COUNT(*) as count,
         SUM(amount) as total,
         AVG(amount) as avg
  FROM stdin
  GROUP BY category
" | jn put summary.json
```

This would compile to the jq equivalent internally.

## Common Pitfalls

### 1. Forgetting `-s` (Slurp)

```bash
# ❌ Wrong - processes each record individually
jn cat data.csv | jq 'group_by(.category)'

# ✅ Right - slurps all records into array first
jn cat data.csv | jq -s 'group_by(.category)'
```

### 2. Division by Zero

```bash
# ❌ Wrong - crashes if group is empty
(map(.amount) | add) / length

# ✅ Right - handle empty groups
if length > 0 then (map(.amount) | add) / length else 0 end
```

### 3. Null Handling

```bash
# ❌ Wrong - fails if amount is null
map(.amount) | add

# ✅ Right - filter nulls first
map(select(.amount != null) | .amount) | add // 0
```

## Testing Aggregations

```bash
# Test with sample data
echo '{"category":"A","amount":100}
{"category":"A","amount":200}
{"category":"B","amount":150}' | \
jn cat - | jq -s 'group_by(.category) | map({
  category: .[0].category,
  total: map(.amount) | add
})'

# Expected output:
# [
#   {"category": "A", "total": 300},
#   {"category": "B", "total": 150}
# ]
```

## Resources

- **jq Manual**: https://jqlang.github.io/jq/manual/
- **jq Cookbook**: https://github.com/stedolan/jq/wiki/Cookbook
- **jq Play**: https://jqplay.org/ (interactive jq playground)

## Success Criteria

- [x] Users can perform common aggregations with documented jq patterns
- [x] Patterns cover: COUNT, SUM, AVG, MAX, MIN, GROUP BY
- [x] Examples show single and multi-field grouping
- [x] Pivot table examples included
- [x] Integration with JN commands (cat, put)
- [x] Clear error handling patterns
- [x] Performance guidance (when to use SQL instead)

## Future Enhancements

**If users request it** (not in initial release):
- Optional SQL-like aggregation syntax that compiles to jq
- Built-in aggregation functions in JN (avoiding `-s` requirement)
- Streaming aggregations for very large files
- Interactive pivot table builder (CLI wizard)
