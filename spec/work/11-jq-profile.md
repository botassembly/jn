# JQ Profile System

## What
Named jq filter library with reusable transformations. Store custom jq scripts as profiles, invoke by name.

## Why
Common transformations (pivot tables, grouping, aggregations) get reused. Enable filter libraries instead of rewriting jq expressions.

## Key Features
- Named jq filters in profile directory (`profiles/jq/myfilters/pivot.jq`)
- Invoke with `@myfilters/pivot` syntax
- Parameter substitution in jq scripts
- Built-in common transformations (pivot table, group_by, stats)
- Documentation embedded in filter files

## Profile Structure
**Filter:** `profiles/jq/analytics/pivot.jq`
```jq
# Pivot table: Convert array of objects to pivoted structure
# Parameters: row_key, col_key, value_key
group_by(.[$row_key]) | map({
  key: .[0][$row_key],
  values: group_by(.[$col_key]) | map({
    key: .[0][$col_key],
    value: map(.[$value_key]) | add
  }) | from_entries
}) | from_entries
```

## Examples
```bash
# Use named filter
jn cat sales.csv | jn filter @analytics/pivot --row product --col month --value revenue

# Built-in pivot transformation
jn cat data.json | jn filter @builtin/pivot --row region --col quarter --value sales

# Group and aggregate
jn cat orders.csv | jn filter @analytics/group_sum --by customer --sum total

# Chain custom filters
jn cat logs.json | jn filter @parsing/extract_errors | jn filter @analytics/count_by_type
```

## Built-in Filters
Include common transformations:
- **pivot** - Pivot table (row/col/value)
- **group_sum** - Group by key and sum values
- **group_count** - Count occurrences by key
- **flatten_nested** - Flatten nested objects
- **stats** - Basic statistics (min, max, avg, sum, count)

## Pivot Table Documentation
Pivot tables reshape data from long to wide format:
- **Row key**: Field to become row labels
- **Column key**: Field to become column headers
- **Value key**: Field to aggregate in cells

Example transformation:
```
Input:  [{"region":"West","month":"Jan","sales":100}, {"region":"West","month":"Feb","sales":150}]
Output: {"West": {"Jan": 100, "Feb": 150}}
```

## Out of Scope
- Complex statistical functions (use dedicated tools)
- Custom jq modules/imports (basic filters only)
