#!/bin/bash
# Dead Code Analysis Demo
# Demonstrates using Tree-sitter + LCOV plugins for coverage analysis

set -e
cd "$(dirname "$0")/../.."

echo "=== Dead Code Analysis Demo ==="
echo ""

# Ensure we have coverage data
if [ ! -f coverage.lcov ]; then
    echo "No coverage.lcov found. Run 'make coverage' first."
    exit 1
fi

echo "1. Find all unexecuted functions across the codebase"
echo "   (Functions that exist in coverage but were never called)"
echo ""
cat coverage.lcov | uv run --script jn_home/plugins/formats/lcov_.py --mode read 2>/dev/null | \
    jq -c 'select(.executed==false) | {file, function, coverage, missing_lines}' | \
    head -10
echo ""

echo "2. Extract symbols from a specific file using Tree-sitter"
echo "   (Get function definitions with line numbers)"
echo ""
cat src/jn/plugins/discovery.py | \
    uv run --script jn_home/plugins/formats/treesitter_.py --mode read --output-mode symbols --filename discovery.py 2>/dev/null | \
    jq -c 'select(.type=="function") | {name, start_line, end_line, lines}'
echo ""

echo "3. Join symbols with coverage data"
echo "   (Enrich function definitions with their coverage)"
echo ""

# Prepare temp files for join
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# Extract symbols with function field
cat src/jn/plugins/discovery.py | \
    uv run --script jn_home/plugins/formats/treesitter_.py --mode read --output-mode symbols --filename discovery.py 2>/dev/null | \
    jq -c 'select(.function)' > "$TMPDIR/symbols.ndjson"

# Extract coverage for same file
cat coverage.lcov | \
    uv run --script jn_home/plugins/formats/lcov_.py --mode read 2>/dev/null | \
    jq -c 'select(.file | contains("plugins/discovery"))' > "$TMPDIR/lcov.ndjson"

# Join on function field (simple --on syntax)
cat "$TMPDIR/symbols.ndjson" | \
    uv run jn join "$TMPDIR/lcov.ndjson" \
        --on function --target coverage --pick coverage --pick executed | \
    jq -c '{name, lines, coverage: .coverage[0].coverage, executed: .coverage[0].executed}'
echo ""

echo "4. Find lowest coverage functions"
echo "   (Functions with less than 50% coverage)"
echo ""
cat coverage.lcov | uv run --script jn_home/plugins/formats/lcov_.py --mode read 2>/dev/null | \
    jq -c 'select(.coverage < 50 and .executed==true) | {file: (.file | split("/") | .[-1]), function, coverage: (.coverage | floor)}' | \
    head -10
echo ""

echo "5. Cross-file join with composite keys"
echo "   (Using normalized file+function as join key)"
echo ""

# Get symbols from multiple files, adding normalized file field
for f in src/jn/plugins/discovery.py src/jn/core/pipeline.py; do
    cat "$f" | \
        uv run --script jn_home/plugins/formats/treesitter_.py --mode read --output-mode symbols --filename "$(basename $f)" 2>/dev/null | \
        jq -c --arg file "$(basename $f)" 'select(.function) | . + {norm_file: $file}'
done > "$TMPDIR/all_symbols.ndjson"

# Normalize lcov file paths (extract basename)
cat coverage.lcov | uv run --script jn_home/plugins/formats/lcov_.py --mode read 2>/dev/null | \
    jq -c '. + {norm_file: (.file | split("/") | .[-1])}' > "$TMPDIR/all_lcov.ndjson"

# Join with composite key (file + function)
cat "$TMPDIR/all_symbols.ndjson" | \
    uv run jn join "$TMPDIR/all_lcov.ndjson" \
        --on norm_file,function --target coverage --pick coverage --pick executed | \
    jq -c '{file: .norm_file, name, coverage: (.coverage[0].coverage // "N/A" | if type=="number" then floor else . end)}' | \
    head -10
echo ""

echo "=== Demo Complete ==="
echo ""
echo "Key commands:"
echo "  lcov_.py --mode read              Parse LCOV coverage data to NDJSON"
echo "  treesitter_ --output-mode symbols Extract function definitions"
echo "  jn join --on field                Simple join on same field name"
echo "  jn join --on f1,f2                Composite key join (tuple)"
