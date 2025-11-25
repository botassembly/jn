#!/bin/bash
# Coverage Analysis Demo - Using JQ Profiles for Coverage Analysis
#
# Demonstrates:
# - Using JN profiles for coverage.lcov analysis
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

echo "=== JN Coverage Analysis Demo ==="
echo ""
echo "This demo uses 7 JQ profiles to analyze pytest coverage.lcov files."
echo "All profiles work on ANY coverage.lcov file (no hardcoded paths)."
echo ""

# Clean up previous output
rm -f uncovered.json low_coverage.lcov poor_branches.json gaps.json hotspots.json summary.json coverage_ranges.json

# Example 1: Find all uncovered functions (0% coverage)
echo "1. Find functions with 0% coverage..."
$JN cat coverage.lcov | \
  $JN filter '@lcov/uncovered-functions' | \
  $JN put uncovered.json
COUNT=$(jq '. | length' uncovered.json)
echo "   ✓ Found $COUNT uncovered functions → uncovered.json"
echo "   Sample:"
$JN cat uncovered.json | $JN head -n 3
echo ""

# Example 2: Functions below coverage threshold
echo "2. Find functions below 60% coverage..."
$JN cat coverage.lcov | \
  $JN filter '@lcov/functions-below-threshold?threshold=60' | \
  $JN put low_coverage.lcov
COUNT=$(jq '. | length' low_coverage.lcov)
echo "   ✓ Found $COUNT functions below 60% → low_coverage.lcov"
echo "   Sample (worst offenders):"
$JN cat low_coverage.lcov | $JN filter 'select(.coverage < 20)' | $JN head -n 3
echo ""

# Example 3: Files grouped by coverage ranges
echo "3. Group files by coverage ranges..."
$JN cat coverage.lcov | \
  $JN filter '@lcov/files-by-coverage' | \
  $JN put coverage_ranges.json
echo "   ✓ Coverage distribution → coverage_ranges.json"
jq -r '.[] | "   \(.range): \(.count) files (avg: \(.avg_coverage)%)"' coverage_ranges.json
echo ""

# Example 4: Poor branch coverage
echo "4. Find functions with poor branch coverage (<70%)..."
$JN cat coverage.lcov | \
  $JN filter '@lcov/poor-branch-coverage?threshold=70' | \
  $JN put poor_branches.json
COUNT=$(jq '. | length' poor_branches.json)
echo "   ✓ Found $COUNT functions with poor branch coverage → poor_branches.json"
echo "   Sample (worst branch coverage):"
$JN cat poor_branches.json | jq -s 'sort_by(.branch_coverage) | .[:3] | .[]' | \
  jq -r '"   \(.file):\(.function) - \(.branch_coverage)% (\(.partial_branches) partial branches)"'
echo ""

# Example 5: Largest coverage gaps
echo "5. Find functions with most missing lines (3+ uncovered lines)..."
$JN cat coverage.lcov | \
  $JN filter '@lcov/largest-gaps?min_missing=3' | \
  $JN put gaps.json
COUNT=$(jq '. | length' gaps.json)
echo "   ✓ Found $COUNT functions with significant gaps → gaps.json"
echo "   Sample (largest gaps):"
$JN cat gaps.json | jq -s 'sort_by(.missing) | reverse | .[:3] | .[]' | \
  jq -r '"   \(.file):\(.function) - \(.missing) lines missing (\(.uncovered_pct)% uncovered)"'
echo ""

# Example 6: Module-level summary
echo "6. Generate module-level coverage summary..."
$JN cat coverage.lcov | \
  $JN filter '@lcov/summary-by-module' | \
  $JN put summary.json
echo "   ✓ Module summary → summary.json"
echo ""
echo "   Coverage by module:"
jq -r '.[] | "   \(.module ): \(.coverage)% (\(.covered)/\(.statements) lines, \(.branch_coverage)% branches)"' \
  summary.json 2>/dev/null || \
  jq -r '.[] | "   " + .module + ": " + (.coverage|tostring) + "% (" + (.covered|tostring) + "/" + (.statements|tostring) + " lines)"' summary.json
echo ""

# Example 7: Coverage hotspots (large functions with low coverage)
echo "7. Identify coverage hotspots (10+ statements, <70% coverage)..."
$JN cat coverage.lcov | \
  $JN filter '@lcov/hotspots?min_statements=10&max_coverage=70' | \
  $JN put hotspots.json
COUNT=$(jq '. | length' hotspots.json)
echo "   ✓ Found $COUNT hotspot functions → hotspots.json"
echo "   Sample (highest priority):"
$JN cat hotspots.json | jq -s 'sort_by(.complexity_score) | reverse | .[:3] | .[]' | \
  jq -r '"   \(.priority | ascii_upcase): \(.file):\(.function) - \(.statements) statements, \(.coverage)% coverage (score: \(.complexity_score))"'
echo ""

# Example 8: Combined workflow - generate a coverage report
echo "8. Generate comprehensive coverage report..."
{
  echo "# Coverage Analysis Report"
  echo ""
  echo "## Summary Statistics"
  echo ""
  echo "- **Uncovered functions**: $COUNT uncovered"
  TOTAL_LOW=$(jq '. | length' low_coverage.lcov)
  echo "- **Functions below 60%**: $TOTAL_LOW functions"
  TOTAL_HOTSPOTS=$(jq '. | length' hotspots.json)
  echo "- **Coverage hotspots**: $TOTAL_HOTSPOTS large under-tested functions"
  echo ""

  echo "## Coverage Distribution"
  echo ""
  echo "\`\`\`"
  jq -r '.[] | "\(.range ) : \(.count) files (avg: \(.avg_coverage)%)"' coverage_ranges.json
  echo "\`\`\`"
  echo ""

  echo "## Module Coverage"
  echo ""
  echo "\`\`\`"
  jq -r '.[] | "\(.module ) : \(.coverage)%"' summary.json
  echo "\`\`\`"
  echo ""

  echo "## Priority Functions to Test"
  echo ""
  echo "### Critical Hotspots"
  echo ""
  jq -s '.[] | select(.priority == "critical")' hotspots.json | \
    jq -r '"- \(.file):\(.function) (\(.statements) statements, \(.coverage)% coverage)"' || \
    echo "(none)"
  echo ""

  echo "### High Priority Hotspots"
  echo ""
  jq -s '.[] | select(.priority == "high") | "\(.file):\(.function) (\(.statements) statements, \(.coverage)% coverage)"' hotspots.json | \
    head -5 | sed 's/^/- /' || \
    echo "(none)"
  echo ""
} > coverage_report.md

echo "   ✓ Generated coverage_report.md"
echo ""

# Example 9: Export to CSV for spreadsheets
echo "9. Export results to CSV for spreadsheet analysis..."
$JN cat hotspots.json | $JN put hotspots.csv
$JN cat summary.json | $JN put summary.csv
echo "   ✓ Created hotspots.csv and summary.csv"
echo ""

# Show final summary
echo "=== Demo Complete ==="
echo ""
echo "Generated files:"
echo "  - uncovered.json           : Functions with 0% coverage"
echo "  - low_coverage.lcov        : Functions below 60% threshold"
echo "  - coverage_ranges.json     : Files grouped by coverage ranges"
echo "  - poor_branches.json       : Functions with poor branch coverage"
echo "  - gaps.json                : Functions with most missing lines"
echo "  - summary.json             : Module-level coverage summary"
echo "  - hotspots.json            : Large under-tested functions"
echo "  - coverage_report.md       : Comprehensive markdown report"
echo "  - hotspots.csv, summary.csv: CSV exports for spreadsheets"
echo ""
echo "Try these commands:"
echo "  $JN cat coverage.lcov | $JN filter '@lcov/uncovered-functions'"
echo "  $JN cat coverage.lcov | $JN filter '@lcov/functions-below-threshold?threshold=80'"
echo "  $JN cat coverage.lcov | $JN filter '@lcov/summary-by-module'"
echo "  $JN cat coverage.lcov | $JN filter '@lcov/hotspots'"
echo ""
echo "All profiles work on ANY coverage.lcov file - try them on your own project!"
