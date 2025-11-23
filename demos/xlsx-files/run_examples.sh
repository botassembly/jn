#!/bin/bash
# XLSX Demo - Run Examples

set -e

echo "=== JN XLSX Demo ==="
echo ""

# Create sample Excel file
echo "Creating sample budget.xlsx file..."
python3 create_sample.py
echo ""

# Clean up previous output
rm -f budget.csv budget.json engineering.csv category_totals.json monthly_totals.json

echo "1. View Excel data (first 5 rows)..."
jn cat budget.xlsx | jn head -n 5
echo ""

echo "2. Convert Excel to CSV..."
jn cat budget.xlsx | jn put budget.csv
echo "   ✓ Created budget.csv"
echo ""

echo "3. Convert Excel to JSON..."
jn cat budget.xlsx | jn put budget.json
echo "   ✓ Created budget.json"
echo ""

echo "4. Filter Engineering expenses..."
jn cat budget.xlsx | \
  jn filter 'select(.Category == "Engineering")' | \
  jn put engineering.csv
echo "   ✓ Created engineering.csv"
echo ""

echo "5. Calculate totals by category..."
jn cat budget.xlsx | \
  jq -s 'group_by(.Category) | map({
    category: .[0].Category,
    total: map(.Amount | tonumber) | add,
    count: length
  })' > category_totals.json
echo "   ✓ Created category_totals.json"
echo ""

echo "6. Calculate monthly totals..."
jn cat budget.xlsx | \
  jq -s 'group_by(.Month) | map({
    month: .[0].Month,
    total: map(.Amount | tonumber) | add,
    items: length
  })' > monthly_totals.json
echo "   ✓ Created monthly_totals.json"
echo ""

echo "=== Results ==="
echo ""

echo "Total records: $(jn cat budget.xlsx | jq -s 'length')"
echo ""

echo "Total budget: \$$(jn cat budget.xlsx | jq -s 'map(.Amount | tonumber) | add')"
echo ""

echo "Top category by spending:"
jq 'sort_by(.total) | reverse | .[0] | "\(.category): $\(.total)"' category_totals.json
echo ""

echo "Engineering expenses:"
jn cat engineering.csv | jq -s 'length' | xargs echo "  Count:"
jn cat engineering.csv | jq -s 'map(.Amount | tonumber) | add' | xargs echo "  Total: $"
echo ""

echo "All examples completed! Check the output files."
