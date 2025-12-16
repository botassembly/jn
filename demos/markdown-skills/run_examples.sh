#!/bin/bash
# Markdown Skills Demo - Query folders of markdown files with YAML front matter
#
# Demonstrates:
# - Querying markdown files with YAML front matter
# - Extracting metadata from skill files
# - Filtering and searching across skills
# - Creating folder profiles for markdown collections

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
    echo "Error: jn-cat not found. Run 'make build' or 'make tool-jn-cat' first."
    exit 1
fi

echo "=== Markdown Skills Demo ==="
echo ""
echo "This demo uses skill files from https://github.com/anthropics/skills"
echo "Each SKILL.md has YAML front matter with: name, description, license"
echo ""

# Setup output directory
mkdir -p output .jn/profiles/file/skills

# ============================================================================
# Create folder profiles for skills
# ============================================================================

echo "Setting up folder profiles..."

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

echo "   Created profiles in .jn/profiles/file/skills/"
echo ""

# ============================================================================
# Run examples
# ============================================================================

echo "1. List all skills (frontmatter only)..."
$JN_CAT '@skills/catalog' 2>/dev/null > output/skills_catalog.jsonl
SKILL_COUNT=$(wc -l < output/skills_catalog.jsonl)
echo "   Found $SKILL_COUNT skills"
echo ""

echo "2. Show skill names and descriptions..."
$JN_CAT '@skills/catalog' 2>/dev/null | $JN_FILTER '{name: .name, description: .description[0:80]}' 2>/dev/null > output/skills_summary.jsonl
head -5 output/skills_summary.jsonl
echo "   ..."
echo ""

echo "3. Find PDF-related skills..."
$JN_CAT '@skills/pdf-related' 2>/dev/null > output/pdf_skills.jsonl 2>/dev/null || true
PDF_COUNT=$(wc -l < output/pdf_skills.jsonl 2>/dev/null || echo 0)
echo "   Found $PDF_COUNT PDF-related skills"
if [ -s output/pdf_skills.jsonl ]; then
    head -2 output/pdf_skills.jsonl | $JN_FILTER '.name' 2>/dev/null
fi
echo ""

echo "4. Find web-related skills..."
$JN_CAT '@skills/web-related' 2>/dev/null > output/web_skills.jsonl 2>/dev/null || true
WEB_COUNT=$(wc -l < output/web_skills.jsonl 2>/dev/null || echo 0)
echo "   Found $WEB_COUNT web-related skills"
if [ -s output/web_skills.jsonl ]; then
    head -3 output/web_skills.jsonl | $JN_FILTER '.name' 2>/dev/null
fi
echo ""

echo "5. Query single markdown file directly..."
$JN_CAT data/pdf/SKILL.md 2>/dev/null | head -1 | $JN_FILTER '{name: .name, type: .type}' 2>/dev/null
echo ""

echo "6. Show file structure with metadata..."
$JN_CAT 'data/**/SKILL.md' --meta 2>/dev/null | $JN_FILTER 'select(.type == "frontmatter") | {skill: .name, file: ._filename, dir: ._dir}' 2>/dev/null | head -5
echo ""

# ============================================================================
# Show what profiles look like
# ============================================================================

echo "=== Profile Structure ==="
echo ""
echo "Skills folder profiles are at: .jn/profiles/file/skills/"
ls -la .jn/profiles/file/skills/
echo ""

echo "=== Example Profile (skills/catalog.json) ==="
cat .jn/profiles/file/skills/catalog.json | jq . 2>/dev/null || cat .jn/profiles/file/skills/catalog.json
echo ""

echo "=== Data Structure ==="
echo ""
echo "Markdown files with YAML front matter:"
echo ""
echo "---"
head -6 data/pdf/SKILL.md
echo "---"
echo "(content continues...)"
echo ""

# ============================================================================
# Advanced queries
# ============================================================================

echo "=== Advanced Queries ==="
echo ""

echo "7. Group skills by license type..."
$JN_CAT '@skills/catalog' 2>/dev/null | $JN_FILTER '.license' 2>/dev/null | sort | uniq -c | head -5
echo ""

echo "8. Skills with longest descriptions..."
$JN_CAT '@skills/catalog' 2>/dev/null | $JN_FILTER '{name: .name, desc_len: (.description | length)}' 2>/dev/null | $JN_FILTER 'select(.desc_len > 100)' 2>/dev/null | head -3
echo ""

# Show jn-inspect output
echo "=== Profile Discovery ==="
echo ""
echo "jn-inspect profiles --type=file:"
../../dist/bin/jn-inspect profiles --type=file 2>/dev/null || echo "(jn-inspect not available)"
echo ""

# Cleanup option
if [ "$1" = "--cleanup" ]; then
    echo "Cleaning up..."
    rm -rf output .jn
    echo "Done."
fi

echo "All examples completed! Check output/ directory for results."
echo "Run with --cleanup to remove generated files."
