#!/bin/bash
# JSON Editing Demo - Surgical JSON Modifications with jn-edit
set -e
cd "$(dirname "$0")"

rm -f actual.txt

echo "=== JSON Editing Demo ===" >> actual.txt
echo "" >> actual.txt

echo "1. Set a string value:" >> actual.txt
jn cat sample.json | jn edit .name=Bob >> actual.txt
echo "" >> actual.txt

echo "2. Set a numeric value (use :=):" >> actual.txt
jn cat sample.json | jn edit .age:=25 >> actual.txt
echo "" >> actual.txt

echo "3. Set a nested field:" >> actual.txt
jn cat sample.json | jn edit .profile.location=Boston >> actual.txt
echo "" >> actual.txt

echo "4. Delete a field:" >> actual.txt
jn cat sample.json | jn edit --del .email >> actual.txt
echo "" >> actual.txt

echo "5. Multiple edits in one command:" >> actual.txt
jn cat sample.json | jn edit .name=Charlie .age:=35 >> actual.txt
echo "" >> actual.txt

echo "6. Append to an array:" >> actual.txt
jn cat sample.json | jn edit --append .tags moderator >> actual.txt
echo "" >> actual.txt

echo "7. Merge a partial object:" >> actual.txt
jn cat sample.json | jn edit --merge '{"name": "Eve", "age": 28}' >> actual.txt
echo "" >> actual.txt

echo "8. Edit all records in NDJSON stream:" >> actual.txt
jn cat users.jsonl | jn edit .verified:=true >> actual.txt
echo "" >> actual.txt

echo "=== Done ===" >> actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
