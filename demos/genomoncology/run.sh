#!/bin/bash
# GenomOncology Profile Demo - HTTP Profile Configuration Example
# Note: This demo shows profile structure. Actual API access requires credentials.
set -e
cd "$(dirname "$0")"

rm -f actual.txt

echo "=== GenomOncology Profile Demo ===" >> actual.txt
echo "" >> actual.txt

echo "1. Profile metadata (_meta.json):" >> actual.txt
cat profiles/http/genomoncology/_meta.json >> actual.txt
echo "" >> actual.txt
echo "" >> actual.txt

echo "2. Available endpoints:" >> actual.txt
ls -1 profiles/http/genomoncology/*.json | xargs -n1 basename | grep -v _meta | sort >> actual.txt
echo "" >> actual.txt

echo "3. Alterations endpoint config:" >> actual.txt
cat profiles/http/genomoncology/alterations.json >> actual.txt
echo "" >> actual.txt
echo "" >> actual.txt

echo "4. Clinical trials endpoint config:" >> actual.txt
cat profiles/http/genomoncology/clinical_trials.json >> actual.txt
echo "" >> actual.txt
echo "" >> actual.txt

echo "5. Example usage (requires credentials):" >> actual.txt
echo '  jn cat @genomoncology/alterations?gene=BRAF' >> actual.txt
echo '  jn cat @genomoncology/clinical_trials?gene=EGFR' >> actual.txt
echo '  jn cat @genomoncology/genes?symbol=TP53' >> actual.txt
echo "" >> actual.txt

echo "=== Done ===" >> actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
