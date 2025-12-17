#!/bin/bash
# Folder Profiles Demo - Query JSONL folders with named profiles
set -e
cd "$(dirname "$0")"

rm -f actual.txt

echo "=== Folder Profiles Demo ===" >> actual.txt
echo "" >> actual.txt

echo "1. Query all events (count):" >> actual.txt
jn cat @events/all | jn filter -s 'length' >> actual.txt
echo "" >> actual.txt

echo "2. Query login events only:" >> actual.txt
jn cat @events/logins | jn filter '{event_type, user_id, ip}' >> actual.txt
echo "" >> actual.txt

echo "3. Query order events:" >> actual.txt
jn cat @events/orders | jn filter '{event_type, order_id, total}' >> actual.txt
echo "" >> actual.txt

echo "4. Query January events (count by type):" >> actual.txt
jn cat @events/january | jn filter -s 'group_by(.event_type) | map({type: .[0] | .event_type, count: length})' >> actual.txt
echo "" >> actual.txt

echo "5. Query CPU metrics:" >> actual.txt
jn cat @metrics/cpu | jn filter '{host, value}' >> actual.txt
echo "" >> actual.txt

echo "6. Query high CPU (>50%):" >> actual.txt
jn cat @metrics/high_cpu | jn filter '{host, value}' >> actual.txt
echo "" >> actual.txt

echo "7. Example profile definition:" >> actual.txt
cat .jn/profiles/file/events/logins.json >> actual.txt
echo "" >> actual.txt

echo "=== Done ===" >> actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
