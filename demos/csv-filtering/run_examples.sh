#!/bin/bash
# CSV Filtering Demo - Core JN ETL Operations
#
# Demonstrates:
# - Reading CSV files into NDJSON streams
# - Filtering with jq expressions
# - Converting between formats (CSV, JSON)
# - Aggregating data
# - Multi-stage pipelines

set -e

echo "=== JN CSV Filtering Demo ==="
echo ""

# Clean up previous output
rm -f electronics.json high_revenue.json summary.json top_products.csv

# Example 1: Simple filtering
# jn cat reads CSV → NDJSON stream
# jn filter applies jq expression to each record
# select() passes through only matching records (not true/false!)
# jn put writes NDJSON → JSON array
echo "1. Filter Electronics products..."
jn cat sales_data.csv | \
  jn filter 'select(.category == "Electronics")' | \
  jn put electronics.json
echo "   ✓ Created electronics.json"
echo ""

# Example 2: Numeric filtering
# Convert string to number with |tonumber before comparison
# select() ensures we pass through records, not booleans
echo "2. Filter high-revenue products (>$100)..."
jn cat sales_data.csv | \
  jn filter 'select((.revenue | tonumber) > 100)' | \
  jn put high_revenue.json
echo "   ✓ Created high_revenue.json"
echo ""

# Example 3: Streaming with head
# jn head limits output (early termination - upstream stops after 5)
echo "3. Show first 5 records:"
jn cat sales_data.csv | jn head -n 5
echo ""

# Example 4: Aggregation with jq
# jq -s slurps entire stream into array for grouping
# Direct file redirect (>) instead of jn put for non-NDJSON output
echo "4. Generate summary statistics..."
jn cat sales_data.csv | \
  jq -s '{
    total_records: length,
    total_revenue: map(.revenue | tonumber) | add,
    total_units: map(.units | tonumber) | add,
    categories: (group_by(.category) | map({
      category: .[0].category,
      count: length,
      revenue: map(.revenue | tonumber) | add
    })),
    regions: (group_by(.region) | map({
      region: .[0].region,
      count: length,
      revenue: map(.revenue | tonumber) | add
    }))
  }' > summary.json
echo "   ✓ Created summary.json"
echo ""

# Example 5: Transform → Sort → Limit
# Add calculated field, sort by it, take top 5
# jq -sc: slurp + compact output (NDJSON)
echo "5. Top 5 products by total sales..."
jn cat sales_data.csv | \
  jn filter '. + {total: ((.revenue | tonumber) * (.units | tonumber))}' | \
  jq -sc 'sort_by(.total) | reverse | .[:5] | .[]' | \
  jn put top_products.csv
echo "   ✓ Created top_products.csv"
echo ""

# Show results
echo "=== Results ==="
echo ""
echo "Electronics count: $(jq 'length' electronics.json)"
echo "High revenue count: $(jq 'length' high_revenue.json)"
echo "Total revenue: \$$(jq -r '.total_revenue' summary.json)"
echo "Total units: $(jq -r '.total_units' summary.json)"
echo ""
echo "Top product by sales:"
jn cat top_products.csv | jn head -n 1 | jq -r '"\(.product): $\(.total)"'
echo ""

echo "All examples completed! Check the output files."
