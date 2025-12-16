#!/bin/bash
# Markdown Skills Demo - Query folders of markdown files with YAML front matter
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Get jn-cat path (from dist or dev build)
if [ -f "../../dist/bin/jn-cat" ]; then
    JN_CAT="../../dist/bin/jn-cat"
    JN_FILTER="../../dist/bin/jn-filter"
elif [ -f "../../tools/zig/jn-cat/bin/jn-cat" ]; then
    JN_CAT="../../tools/zig/jn-cat/bin/jn-cat"
    JN_FILTER="../../tools/zig/jn-filter/bin/jn-filter"
else
    echo "Error: jn-cat not found. Run 'make build' first."
    exit 1
fi

run() {
    echo "\$ $*"
    "$@" 2>/dev/null | sed "s|$SCRIPT_DIR/||g"
    echo ""
}

echo "=== Markdown Skills Demo ==="
echo ""

echo "# List all skills (frontmatter only)"
run $JN_CAT '@skills/catalog'

echo "# Show skill names only"
run sh -c "$JN_CAT '@skills/catalog' 2>/dev/null | $JN_FILTER '.name' 2>/dev/null"

echo "# Query single markdown file"
run sh -c "$JN_CAT data/pdf/SKILL.md 2>/dev/null | head -1 | $JN_FILTER '{name: .name, type: .type}' 2>/dev/null"

echo "=== Profile Structure ==="
echo ""
run find .jn/profiles/file/skills -name '*.json' | sort

echo "# Example profile: skills/catalog.json"
run cat .jn/profiles/file/skills/catalog.json
