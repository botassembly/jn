#!/bin/bash
# demo/coverage.sh - Function-level coverage analysis using tree-sitter + jn join
#
# This demo shows how to use tree-sitter for code structure extraction
# and jn join for range-based coverage analysis - works with any LCOV file.

set -e

# Ensure coverage data exists
if [ ! -f coverage.lcov ]; then
    echo "coverage.lcov not found. Run: make coverage"
    exit 1
fi

JN="uv run python -m jn.cli.main"

echo "=== Function Coverage Report (sample files) ==="
echo ""

# Extract from a few sample files for quick demo
SAMPLE_FILES=(
    "src/jn/filtering.py"
    "src/jn/context.py"
    "src/jn/introspection.py"
    "src/jn/cli/commands/cat.py"
    "src/jn/cli/commands/join.py"
)

(
    for f in "${SAMPLE_FILES[@]}"; do
        if [ -f "$f" ]; then
            $JN plugin call ts_ --mode read --file "$f" 2>/dev/null
        fi
    done
) \
  | $JN join 'coverage.lcov?mode=lines' \
      --on file \
      --where ".line >= .start_line and .line <= .end_line" \
      --agg "total: count, hit: sum(.executed)" \
  | $JN filter '.coverage = (if .total > 0 then ((.hit / .total) * 100 | floor) else 0 end) | {file, function, total, hit, coverage}' \
  | jq -sc 'sort_by(.coverage) | .[]' \
  | $JN put -- '-~table'

echo ""
echo "=== Zero Coverage Functions ==="

(
    for f in "${SAMPLE_FILES[@]}"; do
        if [ -f "$f" ]; then
            $JN plugin call ts_ --mode read --file "$f" 2>/dev/null
        fi
    done
) \
  | $JN join 'coverage.lcov?mode=lines' \
      --on file \
      --where ".line >= .start_line and .line <= .end_line" \
      --agg "total: count, hit: sum(.executed)" \
  | $JN filter 'select(.hit == 0) | {file, function, total}' \
  | $JN put -- '-~table'
