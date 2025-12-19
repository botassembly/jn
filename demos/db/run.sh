#!/bin/bash
# DB Tool Demo - JN-based Document Database
set -e
cd "$(dirname "$0")"

# Use jn tool db (alias is 'db' after source activate.sh)
db() { jn tool db "$@"; }

# Strip ANSI color codes for deterministic output
strip_colors() { sed 's/\x1b\[[0-9;]*m//g'; }

# Clean up any previous test data
rm -f .db.jsonl .db.jsonl.bak .db.jsonl.bak2 .db.jsonl.audit.jsonl .db.jsonl.lock actual.txt

echo "=== DB Demo ===" > actual.txt
echo "" >> actual.txt

echo "1. Initialize database:" >> actual.txt
db init 2>&1 | strip_colors >> actual.txt
echo "" >> actual.txt

echo "2. Insert records:" >> actual.txt
# Capture just the ID assignments, strip timestamps for determinism
db insert '{"name":"Alice","age":30,"role":"engineer"}' 2>&1 | strip_colors | sed 's/"created_at":"[^"]*"/"created_at":"TIMESTAMP"/g; s/"updated_at":"[^"]*"/"updated_at":"TIMESTAMP"/g' >> actual.txt
db insert '{"name":"Bob","age":25,"role":"designer"}' 2>&1 | strip_colors | sed 's/"created_at":"[^"]*"/"created_at":"TIMESTAMP"/g; s/"updated_at":"[^"]*"/"updated_at":"TIMESTAMP"/g' >> actual.txt
db insert '{"name":"Charlie","age":35,"role":"manager"}' 2>&1 | strip_colors | sed 's/"created_at":"[^"]*"/"created_at":"TIMESTAMP"/g; s/"updated_at":"[^"]*"/"updated_at":"TIMESTAMP"/g' >> actual.txt
echo "" >> actual.txt

echo "3. List all records:" >> actual.txt
db list 2>&1 | strip_colors | sed 's/"created_at":"[^"]*"/"created_at":"TIMESTAMP"/g; s/"updated_at":"[^"]*"/"updated_at":"TIMESTAMP"/g' >> actual.txt
echo "" >> actual.txt

echo "4. Get specific record:" >> actual.txt
db get 2 2>&1 | strip_colors | sed 's/"created_at":"[^"]*"/"created_at":"TIMESTAMP"/g; s/"updated_at":"[^"]*"/"updated_at":"TIMESTAMP"/g' >> actual.txt
echo "" >> actual.txt

echo "5. Query with filter:" >> actual.txt
db query 'select(.age > 28)' 2>&1 | strip_colors | sed 's/"created_at":"[^"]*"/"created_at":"TIMESTAMP"/g; s/"updated_at":"[^"]*"/"updated_at":"TIMESTAMP"/g' >> actual.txt
echo "" >> actual.txt

echo "6. Update a record:" >> actual.txt
db set 1 age '31' 2>&1 | strip_colors >> actual.txt
db get 1 2>&1 | strip_colors | sed 's/"created_at":"[^"]*"/"created_at":"TIMESTAMP"/g; s/"updated_at":"[^"]*"/"updated_at":"TIMESTAMP"/g' >> actual.txt
echo "" >> actual.txt

echo "7. Soft delete:" >> actual.txt
db delete 3 2>&1 | strip_colors >> actual.txt
db count 2>&1 | strip_colors >> actual.txt
echo "" >> actual.txt

echo "8. List with deleted:" >> actual.txt
db list --include-deleted 2>&1 | strip_colors | sed 's/"created_at":"[^"]*"/"created_at":"TIMESTAMP"/g; s/"updated_at":"[^"]*"/"updated_at":"TIMESTAMP"/g; s/"deleted_at":"[^"]*"/"deleted_at":"TIMESTAMP"/g' >> actual.txt
echo "" >> actual.txt

echo "9. Undelete:" >> actual.txt
# Use --include-deleted to see deleted records for undelete
db --include-deleted undelete 3 2>&1 | strip_colors >> actual.txt
db count 2>&1 | strip_colors >> actual.txt
echo "" >> actual.txt

echo "10. Stats:" >> actual.txt
db stats 2>&1 | strip_colors >> actual.txt
echo "" >> actual.txt

echo "11. Check integrity:" >> actual.txt
db check 2>&1 | strip_colors >> actual.txt
echo "" >> actual.txt

echo "12. Export as JSON array:" >> actual.txt
db export json 2>&1 | strip_colors | sed 's/"created_at":"[^"]*"/"created_at":"TIMESTAMP"/g; s/"updated_at":"[^"]*"/"updated_at":"TIMESTAMP"/g' >> actual.txt
echo "" >> actual.txt

echo "=== Done ===" >> actual.txt

# Cleanup
rm -f .db.jsonl .db.jsonl.bak .db.jsonl.bak2 .db.jsonl.audit.jsonl .db.jsonl.lock

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
