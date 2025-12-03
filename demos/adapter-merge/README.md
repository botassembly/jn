# Adapter & Merge Demo

Demonstrates JN's unified data orchestration capabilities:

1. **SQL Optional Parameters (Pushdown Adapters)** - Query databases with flexible filters
2. **JQ Profile Substitution (Streaming Adapters)** - Transform data with parameterized profiles
3. **Merge Command (Composability)** - Combine multiple data sources for analysis

## Quick Start

```bash
cd demos/adapter-merge
./run_examples.sh
```

## Features Demonstrated

### 1. SQL Optional Parameters

The optional parameter pattern allows a single SQL query to handle multiple filter scenarios:

```sql
-- profile: @genie/treatment
SELECT * FROM treatments
WHERE ($regimen IS NULL OR regimen = $regimen)
  AND ($min_survival IS NULL OR os_months >= $min_survival);
```

Usage:
```bash
# All records (no filters)
jn cat @genie/treatment

# Filter by regimen
jn cat '@genie/treatment?regimen=FOLFOX'

# Multiple filters
jn cat '@genie/treatment?regimen=FOLFIRI&min_survival=15'
```

### 2. JQ Profile Substitution

Use profile references with string substitution for parameterized filtering:

```jq
# profile: @sales/by_region
select(.region == $region)
```

The `$region` parameter is replaced with the quoted value from the query string.

Usage:
```bash
jn cat sales.csv | jn filter '@sales/by_region?region=East'
# Resolves to: select(.region == "East")
```

### 3. Merge Command

Combine multiple sources with label injection for comparative analysis:

```bash
jn merge \
  'source1.csv:label=GroupA' \
  'source2.csv:label=GroupB'
```

Output includes `_label` and `_source` metadata:
```json
{"id": 1, "value": 100, "_label": "GroupA", "_source": "source1.csv"}
{"id": 2, "value": 200, "_label": "GroupB", "_source": "source2.csv"}
```

## Use Cases

- **Clinical Cohort Analysis**: Compare treatment outcomes across regimens
- **Regional Sales Comparison**: Analyze sales data by region
- **A/B Testing**: Merge and compare test groups
- **Data Quality Checks**: Compare source and target datasets

## Files

- `run_examples.sh` - Main demo script
- `setup_data.py` - Creates test data and profiles
- `profiles/duckdb/genie/` - DuckDB profile with optional params
- `profiles/jq/sales/` - JQ profiles with string substitution
- `sales.csv` - Sample sales data
- `genie.duckdb` - Sample clinical database
