#!/bin/bash
# Code Coverage Analysis Demo
#
# Demonstrates using @code/ profiles with LCOV coverage data:
# - @code/functions - Extract functions with coverage stats
# - @code/calls     - Extract call graph (who calls what)
# - @code/dead      - Find potentially dead code
#
# All output uses jn table for readable formatting.

set -e

# Get absolute paths
DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$DEMO_DIR/../.." && pwd)"

# Install jn as a tool from project root
uv tool install "$PROJECT_ROOT" --force -q

# Run from project root for consistent paths
cd "$PROJECT_ROOT"

# Output file (in demo directory)
OUTPUT="$DEMO_DIR/output.txt"

# Paths relative to project root
SRC_ROOT="src"
LCOV="coverage.lcov"

if [ ! -f "$LCOV" ]; then
    echo "coverage.lcov not found at project root. Run: make coverage"
    exit 1
fi

echo "# Code Coverage Analysis Demo" > "$OUTPUT"
echo "# Generated: $(date)" >> "$OUTPUT"
echo "" >> "$OUTPUT"

# ------------------------------------------------------------------------------
echo "## 1. Low Coverage Functions" | tee -a "$OUTPUT"
echo "# Functions with less than 50% line coverage" >> "$OUTPUT"
echo "" >> "$OUTPUT"

jn cat "@code/functions?root=$SRC_ROOT&lcov=$LCOV" \
  | jn filter 'select(.coverage != null and .coverage < 50)' \
  | jn filter '{file, function, lines, coverage, callers: .caller_count}' \
  | jn table -f simple \
  | tee -a "$OUTPUT"

echo "" >> "$OUTPUT"

# ------------------------------------------------------------------------------
echo "## 2. Zero Coverage Functions" | tee -a "$OUTPUT"
echo "# Functions with 0% coverage (never executed)" >> "$OUTPUT"
echo "" >> "$OUTPUT"

jn cat "@code/functions?root=$SRC_ROOT&lcov=$LCOV" \
  | jn filter 'select(.coverage == 0)' \
  | jn filter '{file, function, lines}' \
  | jn head -n 20 \
  | jn table -f simple \
  | tee -a "$OUTPUT"

echo "" >> "$OUTPUT"

# ------------------------------------------------------------------------------
echo "## 3. Potentially Dead Code" | tee -a "$OUTPUT"
echo "# Functions with no callers (excludes CLI commands, tests, dunders)" >> "$OUTPUT"
echo "" >> "$OUTPUT"

jn cat "@code/dead?root=$SRC_ROOT" \
  | jn filter '{file, function, lines: (.end_line - .start_line + 1)}' \
  | jn head -n 20 \
  | jn table -f simple \
  | tee -a "$OUTPUT"

echo "" >> "$OUTPUT"

# ------------------------------------------------------------------------------
echo "## 4. Most Called Functions" | tee -a "$OUTPUT"
echo "# Functions with the most callers (hot paths)" >> "$OUTPUT"
echo "" >> "$OUTPUT"

jn cat "@code/functions?root=$SRC_ROOT" \
  | jn filter 'select(.caller_count > 0)' \
  | jn filter '{file, function, callers: .caller_count}' \
  | jq -sc 'sort_by(-.callers) | .[0:15] | .[]' \
  | jn table -f simple \
  | tee -a "$OUTPUT"

echo "" >> "$OUTPUT"

# ------------------------------------------------------------------------------
echo "## 5. Call Graph Sample" | tee -a "$OUTPUT"
echo "# Sample of caller -> callee relationships" >> "$OUTPUT"
echo "" >> "$OUTPUT"

jn cat "@code/calls?root=$SRC_ROOT" 2>/dev/null \
  | jn filter '{caller, callee, file}' \
  | jn head -n 20 \
  | jn table -f simple \
  | tee -a "$OUTPUT"

echo "" >> "$OUTPUT"
echo "# Demo complete. Output saved to: $OUTPUT" | tee -a "$OUTPUT"
