#!/bin/bash
# Markdown Demo - Parse markdown with frontmatter into NDJSON
#
# This demo is also an integration test:
# - Outputs to actual.txt
# - Compares against expected.txt
# - Exit 1 if diff found

set -e
cd "$(dirname "$0")"

# Find markdown plugin
find_plugin() {
    local plugin="jn_home/plugins/formats/markdown_.py"
    [ -f "../../$plugin" ] && echo "../../$plugin" && return
    local jn_dir=$(dirname "$(command -v jn 2>/dev/null)")
    [ -f "$jn_dir/../$plugin" ] && echo "$jn_dir/../$plugin" && return
    [ -n "$JN_HOME" ] && [ -f "$JN_HOME/$plugin" ] && echo "$JN_HOME/$plugin" && return
    echo "Error: markdown plugin not found" >&2 && exit 1
}

PLUGIN=$(find_plugin)
md() { uv run "$PLUGIN" "$@" 2>/dev/null; }

# Run demo, capture output
{
echo "=== Markdown Demo ==="
echo ""

echo "1. Frontmatter metadata:"
cat input.md | md --mode read | jq -c 'select(.type=="frontmatter") | {title, version, tags}'
echo ""

echo "2. All headings:"
cat input.md | md --mode read --parse-structure | zq 'select(.type == "heading")' | jq -c '{level, text}'
echo ""

echo "3. Code blocks:"
cat input.md | md --mode read --parse-structure | zq 'select(.type == "code")' | jq -c '{lang: .language}'
echo ""

echo "4. H2+ headings only:"
cat input.md | md --mode read --parse-structure | zq 'select(.type == "heading") | select(.level >= 2)' | jq -c '{level, text}'
echo ""

echo "=== Done ==="
} > actual.txt

# Compare with expected
if [ -f expected.txt ]; then
    if diff -q expected.txt actual.txt > /dev/null; then
        echo "PASS: Output matches expected"
        cat actual.txt
    else
        echo "FAIL: Output differs from expected"
        echo ""
        diff expected.txt actual.txt || true
        exit 1
    fi
else
    echo "No expected.txt - showing output:"
    cat actual.txt
    echo ""
    echo "To create expected.txt: cp actual.txt expected.txt"
fi
