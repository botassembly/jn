#!/bin/bash
# XLSX Demo - Excel Parsing Modes
# Demonstrates all four parsing modes: simple, stats, raw, table
set -e
cd "$(dirname "$0")"

# Create sample Excel files if they don't exist
if [ ! -f budget.xlsx ] || [ ! -f report.xlsx ]; then
    ./create_sample.py
fi

{
echo "=== XLSX Parsing Modes Demo ==="
echo ""

# ============================================================================
# MODE 1: SIMPLE (default) - Treats Excel like CSV
# ============================================================================
echo "=== MODE 1: SIMPLE (default) ==="
echo "Best for: Clean tables with headers in row 1"
echo ""

echo "1a. Read Excel as table (first 3 rows):"
jn cat budget.xlsx | jn head --lines=3
echo ""

echo "1b. Filter and transform:"
jn cat budget.xlsx | jn filter 'select(.Category == "Engineering")' | jn filter '{Month, Amount}'
echo ""

# ============================================================================
# MODE 2: STATS - Inspect workbook structure
# ============================================================================
echo "=== MODE 2: STATS ==="
echo "Best for: Understanding unknown Excel files before parsing"
echo ""

echo "2a. Get workbook overview:"
jn cat 'report.xlsx?mode=stats' | jn filter '{sheet, rows, cols, merged_ranges}'
echo ""

echo "2b. See first row of each sheet (helps identify headers):"
jn cat 'report.xlsx?mode=stats' | jn filter '{sheet, first_row}'
echo ""

# ============================================================================
# MODE 3: RAW - Cell-by-cell output with metadata
# ============================================================================
echo "=== MODE 3: RAW ==="
echo "Best for: Complex/messy spreadsheets, LLM analysis"
echo ""

echo "3a. Inspect cells with types (first 5):"
jn cat 'report.xlsx?mode=raw&sheet=Summary' | jn head --lines=5 | jn filter '{ref, value, type}'
echo ""

echo "3b. Find merged cells:"
jn cat 'report.xlsx?mode=raw&sheet=Summary' | jn filter 'select(.merge != null)' | jn filter '{ref, value, merge, merge_origin}'
echo ""

echo "3c. Find cells with comments:"
jn cat 'report.xlsx?mode=raw&sheet=Summary' | jn filter 'select(.comment != null)' | jn filter '{ref, value, comment}'
echo ""

echo "3d. Find hidden cells:"
jn cat 'report.xlsx?mode=raw&sheet=Notes' | jn filter 'select(.hidden == true)' | jn filter '{ref, value, hidden}'
echo ""

# ============================================================================
# MODE 4: TABLE - Extract specific region
# ============================================================================
echo "=== MODE 4: TABLE ==="
echo "Best for: Extracting data from specific regions with headers"
echo ""

echo "4a. Extract specific range (skip title rows):"
jn cat 'report.xlsx?mode=table&sheet=Summary&range=A4:D8'
echo ""

echo "4b. Extract with column-only range:"
jn cat 'report.xlsx?mode=table&sheet=Monthly&range=A:C' | jn head --lines=2
echo ""

# ============================================================================
# WORKFLOW: Discover then Extract
# ============================================================================
echo "=== WORKFLOW: Discover -> Extract ==="
echo ""

echo "Step 1: Inspect unknown file"
jn cat 'report.xlsx?mode=stats' | jn filter '{sheet, rows, merged_ranges}' | jn head --lines=1
echo ""

echo "Step 2: Raw scan to find data region"
jn cat 'report.xlsx?mode=raw&sheet=Summary&range=A1:A5' | jn filter '{ref, value}'
echo ""

echo "Step 3: Extract clean table (skipping title rows)"
jn cat 'report.xlsx?mode=table&sheet=Summary&range=A4:D8' | jn filter '{Region, "Q4 Total"}'
echo ""

echo "=== Done ==="
} > actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
