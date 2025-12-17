#!/bin/bash
# Markdown Skills - Query markdown files via folder profiles
set -e
cd "$(dirname "$0")"

rm -f actual.txt

echo "=== Markdown Skills Demo ===" >> actual.txt
echo "" >> actual.txt

echo "1. Skill catalog (names):" >> actual.txt
jn cat @skills/catalog | jn filter '{name}' >> actual.txt
echo "" >> actual.txt

echo "2. Total skill count:" >> actual.txt
jn cat @skills/catalog | jn filter -s 'length' >> actual.txt
echo "" >> actual.txt

echo "3. Proprietary skills (have license field):" >> actual.txt
jn cat @skills/catalog | jn filter 'select(.license) | select(.license | contains("Proprietary")) | .name' >> actual.txt
echo "" >> actual.txt

echo "4. First 3 skills:" >> actual.txt
jn cat @skills/catalog | jn filter -s '.[0:3] | .[] | .name' >> actual.txt
echo "" >> actual.txt

echo "5. Average description length:" >> actual.txt
jn cat @skills/catalog | jn filter -s 'map(.description | length) | add / length | floor' >> actual.txt
echo "" >> actual.txt

echo "6. Single file parse (pdf frontmatter):" >> actual.txt
jn cat data/pdf/SKILL.md | jn filter 'select(.type == "frontmatter") | {name, license}' >> actual.txt

echo "" >> actual.txt
echo "=== Done ===" >> actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
