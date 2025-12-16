#!/bin/bash
# Markdown Demo - Parse markdown files with frontmatter into NDJSON
#
# Demonstrates:
# - Extracting frontmatter metadata
# - Parsing document structure (headings, code blocks)
# - Filtering with zq and jq
#
# Prerequisites: jn in PATH (run: source dist/activate.sh)

set -e
cd "$(dirname "$0")"

# Find markdown plugin: check repo layout first, then installed layout
find_plugin() {
    local plugin="jn_home/plugins/formats/markdown_.py"
    # In-repo: demos/markdown-skills -> repo root
    [ -f "../../$plugin" ] && echo "../../$plugin" && return
    # Installed: relative to jn binary
    local jn_dir=$(dirname "$(command -v jn 2>/dev/null)")
    [ -f "$jn_dir/../$plugin" ] && echo "$jn_dir/../$plugin" && return
    # JN_HOME
    [ -n "$JN_HOME" ] && [ -f "$JN_HOME/$plugin" ] && echo "$JN_HOME/$plugin" && return
    echo "Error: markdown plugin not found" >&2 && exit 1
}

PLUGIN=$(find_plugin)
md() { uv run "$PLUGIN" "$@" 2>/dev/null; }

echo "=== Markdown Demo ==="
echo ""

# 1. Extract frontmatter metadata
echo "1. Frontmatter metadata:"
cat sample.md | md --mode read | jq -c 'select(.type=="frontmatter") | {title, version, tags}'
echo ""

# 2. List all headings with zq
echo "2. All headings (using zq select):"
cat sample.md | md --mode read --parse-structure | zq 'select(.type == "heading")' | jq -c '{level, text}'
echo ""

# 3. Extract code blocks with language info
echo "3. Code blocks by language:"
cat sample.md | md --mode read --parse-structure | zq 'select(.type == "code")' | jq -c '{lang: .language}'
echo ""

# 4. Filter h2+ headings only
echo "4. H2+ headings only (level >= 2):"
cat sample.md | md --mode read --parse-structure | zq 'select(.type == "heading") | select(.level >= 2)' | jq -c '{level, text}'
echo ""

# 5. Content preview
echo "5. Content preview (first 100 chars):"
cat sample.md | md --mode read | jq -r 'select(.type=="content") | .content[:100]'
echo "..."
echo ""

echo "=== Demo Complete ==="
