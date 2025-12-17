#!/bin/bash
# XLSX Demo - Working with Excel Files
# Requires: openpyxl (pip install openpyxl)
set -e
cd "$(dirname "$0")"

# Create sample Excel file if it doesn't exist
if [ ! -f budget.xlsx ]; then
    ./create_sample.py
fi

{
echo "=== XLSX Demo ==="
echo ""

echo "1. View Excel data (first 5 rows):"
OUT1=$(jn cat budget.xlsx | jn head --lines=5 | jn filter '{Month, Category, Amount}')
echo "$OUT1"
echo ""

echo "2. Filter Engineering expenses:"
OUT2=$(jn cat budget.xlsx | jn filter 'select(.Category == "Engineering")' | jn filter '{Month, Description, Amount}')
echo "$OUT2"
echo ""

echo "3. Calculate totals by category:"
OUT3=$(jn cat budget.xlsx | jn filter -s 'group_by(.Category) | map({category: .[0] | .Category, total: (map(.Amount | tonumber) | add)}) | sort_by(.category)')
echo "$OUT3"
echo ""

echo "4. Monthly summary:"
OUT4=$(jn cat budget.xlsx | jn filter -s 'group_by(.Month) | map({month: .[0] | .Month, count: length, total: (map(.Amount | tonumber) | add)})')
echo "$OUT4"
echo ""

echo "=== Done ==="
} > actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
