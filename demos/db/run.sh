#!/bin/bash
# DB Tool Demo - JN-based Document Database
# Output format: Data to stdout (NDJSON), Events to stderr (JSONL)
set -e
cd "$(dirname "$0")"

# Use jn tool db (alias is 'db' after source activate.sh)
db() { jn tool db "$@"; }

# Normalize timestamps for deterministic output
normalize() { sed 's/"created_at":"[^"]*"/"created_at":"TS"/g; s/"updated_at":"[^"]*"/"updated_at":"TS"/g; s/"deleted_at":"[^"]*"/"deleted_at":"TS"/g'; }

# Clean up any previous test data
rm -f .db.jsonl .db.jsonl.bak .db.jsonl.bak2 .db.jsonl.audit.jsonl .db.jsonl.lock actual.txt

echo "=== DB Demo ===" > actual.txt
echo "" >> actual.txt

echo "1. Initialize database:" >> actual.txt
# Events go to stderr, capture both (order matters: >> file 2>&1)
db init >> actual.txt 2>&1
echo "" >> actual.txt

echo "2. Insert records:" >> actual.txt
# insert outputs: record to stdout, event to stderr
db insert '{"name":"Alice","age":30,"role":"engineer"}' 2>&1 | normalize >> actual.txt
db insert '{"name":"Bob","age":25,"role":"designer"}' 2>&1 | normalize >> actual.txt
db insert '{"name":"Charlie","age":35,"role":"manager"}' 2>&1 | normalize >> actual.txt
echo "" >> actual.txt

echo "3. List all records:" >> actual.txt
# list outputs: records to stdout only
db list 2>/dev/null | normalize >> actual.txt
echo "" >> actual.txt

echo "4. Get specific record:" >> actual.txt
db get 2 2>/dev/null | normalize >> actual.txt
echo "" >> actual.txt

echo "5. Query with filter:" >> actual.txt
db query 'select(.age > 28)' 2>/dev/null | normalize >> actual.txt
echo "" >> actual.txt

echo "6. Update a record:" >> actual.txt
# set outputs: event to stderr only (use >> file 2>&1 to capture stderr)
db set 1 age '31' >> actual.txt 2>&1
db get 1 2>/dev/null | normalize >> actual.txt
echo "" >> actual.txt

echo "7. Soft delete:" >> actual.txt
db delete 3 >> actual.txt 2>&1
# count outputs: JSON to stdout
db count 2>/dev/null >> actual.txt
echo "" >> actual.txt

echo "8. List with deleted:" >> actual.txt
db list --include-deleted 2>/dev/null | normalize >> actual.txt
echo "" >> actual.txt

echo "9. Undelete:" >> actual.txt
db --include-deleted undelete 3 >> actual.txt 2>&1
db count 2>/dev/null >> actual.txt
echo "" >> actual.txt

echo "10. Stats:" >> actual.txt
# stats outputs: JSON to stdout
db stats 2>/dev/null | sed 's/"file":"[^"]*"/"file":"DB"/g' >> actual.txt
echo "" >> actual.txt

echo "11. Check integrity:" >> actual.txt
# check outputs: JSON to stdout
db check 2>/dev/null >> actual.txt
echo "" >> actual.txt

echo "12. Export as JSON array:" >> actual.txt
db export json 2>/dev/null | normalize >> actual.txt
echo "" >> actual.txt

echo "=== Done ===" >> actual.txt

# Cleanup
rm -f .db.jsonl .db.jsonl.bak .db.jsonl.bak2 .db.jsonl.audit.jsonl .db.jsonl.lock

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
