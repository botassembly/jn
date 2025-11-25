#!/bin/bash
# LCOV Analysis Demo - Using JQ Profiles for Coverage Analysis
#
# Demonstrates:
# - Using JN profiles for LCOV coverage analysis
# - Finding uncovered functions
# - Filtering by coverage thresholds
# - Grouping files by coverage ranges
# - Branch coverage analysis
# - Identifying coverage hotspots
# - Generating module-level summaries

set -e

# Use uv run jn if jn is not in PATH
if ! command -v jn &> /dev/null; then
  JN="uv run jn"
else
  JN="jn"
fi

echo "=== JN LCOV Analysis Demo ==="
echo ""
echo "This demo uses 7 JQ profiles to analyze LCOV coverage files."
echo "All profiles work on ANY coverage.lcov file (no hardcoded paths)."
echo ""

# Clean up previous output
rm -f uncovered.json low_coverage.json poor_branches.json gaps.json hotspots.json summary.json coverage_ranges.json

# Example 1: Find all uncovered functions (0% coverage)
echo "1. Find functions with 0% coverage..."
$JN cat coverage.lcov | \
  $JN filter '@lcov/uncovered-functions' | \
  $JN put uncovered.json
COUNT=$(jq 'length' uncovered.json)
echo "   Found $COUNT uncovered functions -> uncovered.json"
echo "   Sample:"
$JN cat uncovered.json | $JN head -n 3
echo ""

# Example 2: Functions below coverage threshold
echo "2. Find functions below 60% coverage..."
$JN cat coverage.lcov | \
  $JN filter '@lcov/functions-below-threshold?threshold=60' | \
  $JN put low_coverage.json
COUNT=$(jq 'length' low_coverage.json)
echo "   Found $COUNT functions below 60% -> low_coverage.json"
echo "   Sample (worst offenders):"
$JN cat low_coverage.json | $JN filter 'select(.coverage < 20)' | $JN head -n 3
echo ""

# Example 3: Files grouped by coverage ranges
echo "3. Group files by coverage ranges..."
$JN cat coverage.lcov | \
  $JN filter '@lcov/files-by-coverage' | \
  $JN put coverage_ranges.json
echo "   Coverage distribution -> coverage_ranges.json"
$JN cat coverage_ranges.json | $JN head -n 5
echo ""

# Example 4: Poor branch coverage
echo "4. Find functions with poor branch coverage (<70%)..."
$JN cat coverage.lcov | \
  $JN filter '@lcov/poor-branch-coverage?threshold=70' | \
  $JN put poor_branches.json
COUNT=$(jq 'length' poor_branches.json)
echo "   Found $COUNT functions with poor branch coverage -> poor_branches.json"
echo "   Sample:"
$JN cat poor_branches.json | $JN head -n 3
echo ""

# Example 5: Largest coverage gaps
echo "5. Find functions with most missing lines (3+ uncovered lines)..."
$JN cat coverage.lcov | \
  $JN filter '@lcov/largest-gaps?min_missing=3' | \
  $JN put gaps.json
COUNT=$(jq 'length' gaps.json)
echo "   Found $COUNT functions with significant gaps -> gaps.json"
echo "   Sample:"
$JN cat gaps.json | $JN head -n 3
echo ""

# Example 6: Module-level summary
echo "6. Generate module-level coverage summary..."
$JN cat coverage.lcov | \
  $JN filter '@lcov/summary-by-module' | \
  $JN put summary.json
echo "   Module summary -> summary.json"
$JN cat summary.json | $JN head -n 5
echo ""

# Example 7: Coverage hotspots (large functions with low coverage)
echo "7. Identify coverage hotspots (10+ lines, <70% coverage)..."
$JN cat coverage.lcov | \
  $JN filter '@lcov/hotspots?min_lines=10&max_coverage=70' | \
  $JN put hotspots.json
COUNT=$(jq 'length' hotspots.json)
echo "   Found $COUNT hotspot functions -> hotspots.json"
echo "   Sample:"
$JN cat hotspots.json | $JN head -n 3
echo ""

# Show final summary
echo "=== Demo Complete ==="
echo ""
echo "Generated files:"
echo "  - uncovered.json           : Functions with 0% coverage"
echo "  - low_coverage.json        : Functions below 60% threshold"
echo "  - coverage_ranges.json     : Files grouped by coverage ranges"
echo "  - poor_branches.json       : Functions with poor branch coverage"
echo "  - gaps.json                : Functions with most missing lines"
echo "  - summary.json             : Module-level coverage summary"
echo "  - hotspots.json            : Large under-tested functions"
echo ""
echo "Try these commands:"
echo "  $JN cat coverage.lcov | $JN filter '@lcov/uncovered-functions'"
echo "  $JN cat coverage.lcov | $JN filter '@lcov/functions-below-threshold?threshold=80'"
echo "  $JN cat coverage.lcov | $JN filter '@lcov/summary-by-module'"
echo "  $JN cat coverage.lcov | $JN filter '@lcov/hotspots'"
echo ""
echo "All profiles work on ANY coverage.lcov file - try them on your own project!"
