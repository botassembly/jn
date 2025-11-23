#!/bin/bash
# CSV Filtering Demo - Run Examples

set -e

echo "=== JN CSV Filtering Demo ==="
echo ""

# Clean up previous output
rm -f electronics.json high_revenue.json summary.json top_products.csv

echo "1. Filter Electronics products..."
jn cat sales_data.csv | \
  jn filter '.category == "Electronics"' | \
  jn put electronics.json
echo "   ✓ Created electronics.json"
echo ""

echo "2. Filter high-revenue products (>$100)..."
jn cat sales_data.csv | \
  jn filter '(.revenue | tonumber) > 100' | \
  jn put high_revenue.json
echo "   ✓ Created high_revenue.json"
echo ""

echo "3. Show first 5 records:"
jn cat sales_data.csv | jn head -n 5
echo ""

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
  }' | \
  jq '.' | \
  jn put summary.json
echo "   ✓ Created summary.json"
echo ""

echo "5. Top 5 products by total sales..."
jn cat sales_data.csv | \
  jn filter '. + {total: ((.revenue | tonumber) * (.units | tonumber))}' | \
  jq -s 'sort_by(.total) | reverse | .[:5] | .[]' | \
  jn put top_products.csv
echo "   ✓ Created top_products.csv"
echo ""

echo "=== Results ==="
echo ""
echo "Electronics count: $(jq -s 'length' electronics.json)"
echo "High revenue count: $(jq -s 'length' high_revenue.json)"
echo "Total revenue: \$$(jq -r '.total_revenue' summary.json)"
echo "Total units: $(jq -r '.total_units' summary.json)"
echo ""
echo "Top product by sales:"
jn cat top_products.csv | jn head -n 1 | jq -r '"\(.product): $\(.total)"'
echo ""

echo "All examples completed! Check the output files."
