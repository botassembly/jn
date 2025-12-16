#!/bin/bash
# CSV Filtering Demo - Core JN ETL Operations
set -e
cd "$(dirname "$0")"

{
echo "=== CSV Filtering Demo ==="
echo ""

echo "1. Filter Electronics products:"
jn cat input.csv | jn filter 'select(.category == "Electronics")' | jq -c '{product, revenue}'
echo ""

echo "2. High-revenue products (>$100):"
jn cat input.csv | jn filter 'select((.revenue | tonumber) > 100)' | jq -c '{product, revenue}'
echo ""

echo "3. First 5 records:"
jn cat input.csv | jn head --lines=5 | jq -c '{product, category}'
echo ""

echo "4. Summary statistics:"
jn cat input.csv | jq -s '{
  total_records: length,
  total_revenue: (map(.revenue | tonumber) | add | . * 100 | floor / 100),
  categories: (group_by(.category) | length)
}'
echo ""

echo "5. Top 3 products by revenue:"
jn cat input.csv | jq -sc 'sort_by(.revenue | tonumber) | reverse | .[0:3] | .[] | {product, revenue}'
echo ""

echo "=== Done ==="
} > actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
