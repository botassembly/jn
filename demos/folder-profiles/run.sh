#!/bin/bash
# Folder Profiles Demo - Query JSONL folders with named profiles
set -e
cd "$(dirname "$0")"

{
echo "=== Folder Profiles Demo ==="
echo ""

echo "1. Query all events (count):"
jn cat @events/all | jq -s 'length'
echo ""

echo "2. Query login events only:"
jn cat @events/logins | jq -c '{event_type, user_id, ip}'
echo ""

echo "3. Query order events:"
jn cat @events/orders | jq -c '{event_type, order_id, total}'
echo ""

echo "4. Query January events (count by type):"
jn cat @events/january | jq -sc 'group_by(.event_type) | map({type: .[0].event_type, count: length})'
echo ""

echo "5. Query CPU metrics:"
jn cat @metrics/cpu | jq -c '{host, value}'
echo ""

echo "6. Query high CPU (>50%):"
jn cat @metrics/high_cpu | jq -c '{host, value}'
echo ""

echo "7. Example profile definition:"
cat .jn/profiles/file/events/logins.json
echo ""

echo "=== Done ==="
} > actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
