#!/bin/bash
# CSV Filtering Demo - Core JN ETL Operations
set -e
cd "$(dirname "$0")"

rm -f actual.txt

echo "=== CSV Filtering Demo ===" >> actual.txt
echo "" >> actual.txt

echo "1. Filter Electronics products:" >> actual.txt
jn cat input.csv | jn filter 'select(.category == "Electronics")' | jn filter '{product, revenue}' >> actual.txt
echo "" >> actual.txt

echo "2. High-revenue products (>\$100):" >> actual.txt
jn cat input.csv | jn filter 'select((.revenue | tonumber) > 100)' | jn filter '{product, revenue}' >> actual.txt
echo "" >> actual.txt

echo "3. First 5 records:" >> actual.txt
jn cat input.csv | jn head --lines=5 | jn filter '{product, category}' >> actual.txt
echo "" >> actual.txt

echo "4. Summary statistics:" >> actual.txt
jn cat input.csv | jn filter -s '{total_records: length, total_revenue: (map(.revenue | tonumber) | add | . * 100 | floor / 100), categories: (group_by(.category) | length)}' >> actual.txt
echo "" >> actual.txt

echo "5. Top 3 products by revenue:" >> actual.txt
jn cat input.csv | jn filter -s 'map(. + {_n: (.revenue | tonumber)}) | sort_by(._n) | reverse | .[0:3] | .[] | {product, revenue}' >> actual.txt
echo "" >> actual.txt

echo "=== Done ===" >> actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
