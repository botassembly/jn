#!/bin/bash
# XLSX Demo - Working with Excel Files
#
# Demonstrates:
# - Reading Excel (.xlsx) files into NDJSON
# - Converting Excel to CSV/JSON formats
# - Filtering Excel data
# - Aggregating spreadsheet data
# - Requires openpyxl: pip install openpyxl

set -e

echo "=== JN XLSX Demo ==="
echo ""

# Create sample Excel file using Python script (PEP 723 with uv shebang)
echo "Creating sample budget.xlsx file..."
./create_sample.py
echo ""

# Clean up previous output
rm -f budget.csv budget.json engineering.csv category_totals.json monthly_totals.json

# Example 1: View Excel data as NDJSON stream
# jn cat reads .xlsx files via openpyxl plugin
# First row becomes keys, subsequent rows become values
echo "1. View Excel data (first 5 rows)..."
jn cat budget.xlsx | jn head -n 5
echo ""

# Example 2: Excel → CSV conversion
# NDJSON stream → CSV with header row
echo "2. Convert Excel to CSV..."
jn cat budget.xlsx | jn put budget.csv
echo "   ✓ Created budget.csv"
echo ""

# Example 3: Excel → JSON array
# jn put collects NDJSON stream into JSON array
echo "3. Convert Excel to JSON..."
jn cat budget.xlsx | jn put budget.json
echo "   ✓ Created budget.json"
echo ""

# Example 4: Filter Excel rows
# select() passes only matching records through
# Note: Field names match Excel column headers (case-sensitive!)
echo "4. Filter Engineering expenses..."
jn cat budget.xlsx | \
  jn filter 'select(.Category == "Engineering")' | \
  jn put engineering.csv
echo "   ✓ Created engineering.csv"
echo ""

# Example 5: Group and aggregate
# jq -s slurps stream for group_by operation
# Direct output (>) since result is already JSON
echo "5. Calculate totals by category..."
jn cat budget.xlsx | \
  jq -s 'group_by(.Category) | map({
    category: .[0].Category,
    total: map(.Amount | tonumber) | add,
    count: length
  })' > category_totals.json
echo "   ✓ Created category_totals.json"
echo ""

# Example 6: Different grouping dimension
# Same pattern but group by Month instead of Category
echo "6. Calculate monthly totals..."
jn cat budget.xlsx | \
  jq -s 'group_by(.Month) | map({
    month: .[0].Month,
    total: map(.Amount | tonumber) | add,
    items: length
  })' > monthly_totals.json
echo "   ✓ Created monthly_totals.json"
echo ""

# Show results
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
