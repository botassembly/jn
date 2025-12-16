#!/bin/bash
# Markdown Skills - Query markdown files via folder profiles
set -e
cd "$(dirname "$0")"

{
echo "=== Markdown Skills Demo ==="
echo ""

echo "1. Skill catalog (name + short desc):"
jn cat @skills/catalog | jq -c '{name, desc: .description[:50]}'
echo ""

echo "2. Total skill count:"
jn cat @skills/catalog | jq -s 'length'
echo ""

echo "3. Proprietary skills (have license field):"
jn cat @skills/catalog | jq -c 'select(.license) | select(.license | contains("Proprietary")) | .name'
echo ""

echo "4. First 3 skills alphabetically:"
jn cat @skills/catalog | jq -s 'sort_by(.name) | .[0:3] | .[].name'
echo ""

echo "5. Average description length:"
jn cat @skills/catalog | jq -s 'map(.description | length) | add / length | floor'
echo ""

echo "6. Single file parse (pdf frontmatter):"
jn cat data/pdf/SKILL.md | jq -c 'select(.type=="frontmatter") | {name, license}'

echo ""
echo "=== Done ==="
} > actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
