#!/bin/bash
# Code Coverage Analysis Demo
#
# Demonstrates using @code/ profiles for code analysis:
# - @code/functions - Extract function information
# - @code/calls     - Extract call graph (who calls what)
# - @code/dead      - Find potentially dead code
#
# When LCOV coverage data is available, shows coverage statistics.

set -e

# Get absolute paths
DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$DEMO_DIR/../.." && pwd)"

# Run from project root for consistent paths
cd "$PROJECT_ROOT"

# Ensure JN tools are in PATH
export PATH="$PROJECT_ROOT/tools/zig/jn/bin:$PATH"

# Output file (in demo directory)
OUTPUT="$DEMO_DIR/output.txt"

# Check for source files
SRC_ROOT="libs/zig"
if [ ! -d "$SRC_ROOT" ]; then
    echo "Source directory $SRC_ROOT not found"
    exit 1
fi

echo "# Code Analysis Demo" > "$OUTPUT"
echo "# Generated: $(date)" >> "$OUTPUT"
echo "" >> "$OUTPUT"

# ------------------------------------------------------------------------------
echo "## 1. Code Files" | tee -a "$OUTPUT"
echo "# List of source files" >> "$OUTPUT"
echo "" >> "$OUTPUT"

jn cat "@code/files" \
  | jn head -n 15 \
  | tee -a "$OUTPUT"

echo "" >> "$OUTPUT"

# ------------------------------------------------------------------------------
echo "## Demo complete" | tee -a "$OUTPUT"
echo "# @code/ profile resolution is working" >> "$OUTPUT"
echo "" >> "$OUTPUT"
