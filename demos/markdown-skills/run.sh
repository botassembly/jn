#!/bin/bash
# Markdown Skills - Query markdown files via folder profiles
set -e
cd "$(dirname "$0")"

{
echo "=== Markdown Skills Demo ==="
echo ""

echo "1. Skill catalog (name + truncated description):"
jn cat @skills/catalog | jq -c '{name, desc: .description[:50]}'
echo ""

echo "2. Count skills:"
jn cat @skills/catalog | jq -s 'length'
echo ""

echo "3. Single file (pdf skill frontmatter):"
jn cat data/pdf/SKILL.md | jq -c 'select(.type=="frontmatter") | {name, license}'

echo ""
echo "=== Done ==="
} > actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
