#!/bin/bash
# Table Rendering Demo - Pretty-print NDJSON as tables
set -e
cd "$(dirname "$0")"

# Sample data
SAMPLE='{"product":"Widget","price":9.99,"stock":100}
{"product":"Gadget","price":19.99,"stock":50}
{"product":"Gizmo","price":14.99,"stock":75}'

{
echo "=== Table Rendering Demo ==="
echo ""

echo "1. Basic grid table (default):"
OUT1=$(echo "$SAMPLE" | jn table)
echo "$OUT1"
echo ""

echo "2. GitHub markdown table:"
OUT2=$(echo "$SAMPLE" | jn table --tablefmt=github)
echo "$OUT2"
echo ""

echo "3. Simple format (minimal):"
OUT3=$(echo "$SAMPLE" | jn table --tablefmt=simple)
echo "$OUT3"
echo ""

echo "4. Pipeline: filter then table:"
OUT4=$(echo "$SAMPLE" | jn filter 'select(.price > 10)' | jn table)
echo "$OUT4"
echo ""

echo "=== Done ==="
} > actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
