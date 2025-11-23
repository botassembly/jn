# CSV Filtering Demo

This demo demonstrates JN's core ETL capabilities: reading CSV files, filtering data with jq expressions, and outputting to various formats.

## What You'll Learn

- Reading CSV files into NDJSON streams
- Filtering data with jq expressions
- Transforming and reshaping data
- Converting between formats (CSV ↔ JSON ↔ YAML)
- Aggregating and computing statistics

## Sample Data

`sales_data.csv` contains sample sales records with:
- Date of sale
- Product name and category
- Revenue and units sold
- Sales region

## Basic Examples

### 1. View Data as NDJSON

```bash
jn cat sales_data.csv
```

Output:
```json
{"date":"2024-01-15","product":"Laptop Pro","category":"Electronics","revenue":"1299.99","units":"5","region":"North"}
{"date":"2024-01-16","product":"Office Chair","category":"Furniture","revenue":"249.99","units":"12","region":"South"}
...
```

### 2. View First 5 Records

```bash
jn cat sales_data.csv | jn head -n 5
```

### 3. Convert to JSON

```bash
jn cat sales_data.csv | jn put sales_data.json
```

### 4. Convert to YAML

```bash
jn cat sales_data.csv | jn put sales_data.yaml
```

## Filtering Examples

### Filter High-Revenue Items (>$100)

```bash
jn cat sales_data.csv | \
  jn filter '(.revenue | tonumber) > 100'
```

### Filter Electronics Only

```bash
jn cat sales_data.csv | \
  jn filter '.category == "Electronics"'
```

### Filter by Region

```bash
jn cat sales_data.csv | \
  jn filter '.region == "North"'
```

### Multiple Conditions

```bash
jn cat sales_data.csv | \
  jn filter '.category == "Electronics" and (.revenue | tonumber) > 100'
```

## Transformation Examples

### Extract Specific Fields

```bash
jn cat sales_data.csv | \
  jn filter '{product: .product, revenue: .revenue}'
```

### Add Calculated Fields

```bash
jn cat sales_data.csv | \
  jn filter '. + {total: ((.revenue | tonumber) * (.units | tonumber))}'
```

### Reshape Data

```bash
jn cat sales_data.csv | \
  jn filter '{
    item: .product,
    price: .revenue,
    sold: .units,
    where: .region
  }'
```

## Aggregation Examples

### Count Records by Category

```bash
jn cat sales_data.csv | \
  jq -s 'group_by(.category) | map({category: .[0].category, count: length})'
```

### Sum Revenue by Region

```bash
jn cat sales_data.csv | \
  jq -s 'group_by(.region) | map({
    region: .[0].region,
    total_revenue: map(.revenue | tonumber) | add
  })'
```

### Average Units Sold by Category

```bash
jn cat sales_data.csv | \
  jq -s 'group_by(.category) | map({
    category: .[0].category,
    avg_units: (map(.units | tonumber) | add / length)
  })'
```

## Pipeline Examples

### Filter → Transform → Save

```bash
jn cat sales_data.csv | \
  jn filter '.category == "Electronics"' | \
  jn filter '{product: .product, revenue: .revenue}' | \
  jn put electronics.json
```

### Filter → Sort → Limit

```bash
jn cat sales_data.csv | \
  jn filter '(.revenue | tonumber) > 50' | \
  jq -s 'sort_by(.revenue | tonumber) | reverse' | \
  jq '.[]' | \
  jn head -n 5
```

### Multi-stage Transformation

```bash
# 1. Filter electronics
# 2. Add total sales field
# 3. Sort by total
# 4. Save to CSV
jn cat sales_data.csv | \
  jn filter '.category == "Electronics"' | \
  jn filter '. + {total: ((.revenue | tonumber) * (.units | tonumber))}' | \
  jq -s 'sort_by(.total) | reverse | .[]' | \
  jn put top_electronics.csv
```

## Run the Examples

Execute the provided script to run all examples:

```bash
./run_examples.sh
```

This will create output files:
- `electronics.json` - Electronics products only
- `high_revenue.json` - Products with revenue > $100
- `summary.json` - Aggregated statistics
- `top_products.csv` - Top 5 products by total sales

## Key Concepts

### Streaming

JN processes data as a stream, one record at a time:
- **Constant memory** - Works with any file size
- **Immediate output** - First results appear instantly
- **Early termination** - `| head -n 10` stops after 10 records

### NDJSON Format

Newline-Delimited JSON (one object per line):
- Streamable (unlike JSON arrays)
- Human-readable
- Tool-friendly (grep, jq)

### jq Integration

JN uses jq for filtering and transformation:
- Full jq expression syntax
- Access all jq functions (map, select, group_by, etc.)
- Combine multiple filters with `|`

## Next Steps

- Try the HTTP demo for fetching data from APIs
- See the Shell Commands demo for processing command output
- Check the XLSX demo for working with Excel files
