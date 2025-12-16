#!/bin/bash
# Merge Demo - Combining Multiple Data Sources
set -e
cd "$(dirname "$0")"

# Create separate files for comparison
jn cat sales.csv | jn filter 'select(.region == "East")' | jn put /tmp/east_sales.jsonl
jn cat sales.csv | jn filter 'select(.region == "West")' | jn put /tmp/west_sales.jsonl

{
echo "=== Merge Demo ==="
echo ""

echo "1. Merge two files with labels:"
OUT1=$(jn merge "/tmp/east_sales.jsonl:label=East" "/tmp/west_sales.jsonl:label=West" | jq -c '{_label, product, amount}')
echo "$OUT1"
echo ""

echo "2. Count by label (compare regions):"
OUT2=$(jn merge "/tmp/east_sales.jsonl:label=East" "/tmp/west_sales.jsonl:label=West" | jq -s 'group_by(._label) | map({label: .[0]._label, count: length, total: (map(.amount | tonumber) | add)})')
echo "$OUT2"
echo ""

echo "3. Merge without labels (just _source):"
OUT3=$(jn merge /tmp/east_sales.jsonl /tmp/west_sales.jsonl | jn head --lines=3 | jq -c '{_source, product}')
echo "$OUT3"
echo ""

echo "=== Done ==="
} > actual.txt

# Cleanup
rm -f /tmp/east_sales.jsonl /tmp/west_sales.jsonl

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
