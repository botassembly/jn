#!/bin/bash
# HTTP API Demo - Processing JSON API responses
# Uses local mock data for deterministic testing
# In production, use: curl URL | jn filter ...
set -e
cd "$(dirname "$0")"

rm -f actual.txt

{
echo "=== HTTP API Demo ==="
echo ""

echo "1. Parse JSON response (select field):"
OUT1=$(jn cat input.json | jn filter '.slideshow | {title, author}')
echo "$OUT1"
echo ""

echo "2. Extract array elements:"
OUT2=$(jn cat input.json | jn filter '.slideshow.slides[]' | jn filter '{title, type}')
echo "$OUT2"
echo ""

echo "3. Filter and transform:"
OUT3=$(jn cat input.json | jn filter '.slideshow.slides[] | select(.items) | {title, item_count: (.items | length)}')
echo "$OUT3"
echo ""

echo "4. Pipeline with aggregation:"
OUT4=$(jn cat input.json | jn filter '.slideshow.slides[]' | jn filter -s '{total_slides: length, types: (map(.type) | unique)}')
echo "$OUT4"
echo ""

echo "=== Done ==="
} > actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
