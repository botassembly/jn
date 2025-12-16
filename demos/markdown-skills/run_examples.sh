#!/bin/bash
# Markdown Skills Demo - Query folders of markdown files with YAML front matter
#
# Demonstrates:
# - Querying markdown files with YAML front matter
# - Extracting metadata from skill files
# - Filtering and searching across skills
# - Creating folder profiles for markdown collections
#
# Usage:
#   ./run_examples.sh           # Run and display output
#   ./run_examples.sh --cleanup # Clean up generated files

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Get jn-cat path (from dist or dev build)
if [ -f "../../dist/bin/jn-cat" ]; then
    JN_CAT="../../dist/bin/jn-cat"
    JN_FILTER="../../dist/bin/jn-filter"
    JN_INSPECT="../../dist/bin/jn-inspect"
elif [ -f "../../tools/zig/jn-cat/bin/jn-cat" ]; then
    JN_CAT="../../tools/zig/jn-cat/bin/jn-cat"
    JN_FILTER="../../tools/zig/jn-filter/bin/jn-filter"
    JN_INSPECT="../../tools/zig/jn-inspect/bin/jn-inspect"
else
    echo "Error: jn-cat not found. Run 'make build' or 'make tool-jn-cat' first."
    exit 1
fi

# Helper to run and show commands (normalizes paths for portability)
run() {
    echo "\$ $*"
    "$@" | sed "s|$SCRIPT_DIR/||g"
    echo ""
}

echo "=== Markdown Skills Demo ==="
echo ""
echo "# This demo uses skill files from https://github.com/anthropics/skills"
echo "# Each SKILL.md has YAML front matter with: name, description, license"
echo ""

# Setup output directory
mkdir -p output .jn/profiles/file/skills

# ============================================================================
# Create folder profiles for skills
# ============================================================================

echo "# Creating folder profiles..."

# All skills - just frontmatter
cat > .jn/profiles/file/skills/catalog.json << 'EOF'
{
  "pattern": "data/**/SKILL.md",
  "inject_meta": true,
  "filter": "select(.type == \"frontmatter\")",
  "description": "Skill catalog - frontmatter only from all SKILL.md files"
}
EOF

# Skills with "PDF" in description
cat > .jn/profiles/file/skills/pdf-related.json << 'EOF'
{
  "pattern": "data/**/SKILL.md",
  "inject_meta": true,
  "filter": "select(.type == \"frontmatter\" and (.description | test(\"PDF|pdf\"; \"i\")))",
  "description": "Skills related to PDF processing"
}
EOF

# Skills with "web" in name or description
cat > .jn/profiles/file/skills/web-related.json << 'EOF'
{
  "pattern": "data/**/SKILL.md",
  "inject_meta": true,
  "filter": "select(.type == \"frontmatter\" and ((.name | test(\"web\"; \"i\")) or (.description | test(\"web\"; \"i\"))))",
  "description": "Web-related skills"
}
EOF

# All markdown content (not just frontmatter)
cat > .jn/profiles/file/skills/all-content.json << 'EOF'
{
  "pattern": "data/**/*.md",
  "inject_meta": true,
  "description": "All markdown content with file metadata"
}
EOF

echo "# Profiles created in .jn/profiles/file/skills/"
echo ""

# ============================================================================
# Run examples
# ============================================================================

echo "=== Examples ==="
echo ""

echo "# 1. List all skills (frontmatter only)"
run $JN_CAT '@skills/catalog' 2>/dev/null

echo "# 2. Show skill names only"
run sh -c "$JN_CAT '@skills/catalog' 2>/dev/null | $JN_FILTER '.name' 2>/dev/null"

echo "# 3. Query single markdown file directly"
run sh -c "$JN_CAT data/pdf/SKILL.md 2>/dev/null | head -1 | $JN_FILTER '{name: .name, type: .type}' 2>/dev/null"

echo "# 4. Show skill names with file paths"
run sh -c "$JN_CAT '@skills/catalog' 2>/dev/null | $JN_FILTER '{skill: .name, path: ._path}' 2>/dev/null | head -5"

# ============================================================================
# Show profile structure
# ============================================================================

echo "=== Profile Structure ==="
echo ""
echo "# Profiles stored at .jn/profiles/file/skills/"
run find .jn/profiles/file/skills -name '*.json' | sort

echo "# Example: skills/catalog.json"
run cat .jn/profiles/file/skills/catalog.json

# ============================================================================
# Show data structure
# ============================================================================

echo "=== Data Structure ==="
echo ""
echo "# Sample SKILL.md with YAML front matter:"
run head -8 data/pdf/SKILL.md

# ============================================================================
# Profile discovery
# ============================================================================

echo "=== Profile Discovery ==="
echo ""
echo "# jn-inspect profiles --type=file"
run $JN_INSPECT profiles --type=file 2>/dev/null || echo "(jn-inspect not available)"

# Cleanup option
if [ "$1" = "--cleanup" ]; then
    echo "# Cleaning up..."
    rm -rf output .jn
    echo "Done."
fi
