#!/bin/bash
# Glob Demo - Reading Multiple Files with Pattern Matching
set -e
cd "$(dirname "$0")"

# Create deterministic test data
rm -rf test_data
mkdir -p test_data/logs/2024-01 test_data/logs/2024-02

cat > test_data/logs/2024-01/access.jsonl << 'EOF'
{"timestamp": "2024-01-15T10:30:00Z", "level": "INFO", "message": "User login", "user_id": 123}
{"timestamp": "2024-01-15T10:31:00Z", "level": "ERROR", "message": "Connection failed", "user_id": 456}
EOF

cat > test_data/logs/2024-02/access.jsonl << 'EOF'
{"timestamp": "2024-02-01T09:00:00Z", "level": "WARN", "message": "Rate limit", "user_id": 789}
{"timestamp": "2024-02-01T09:05:00Z", "level": "ERROR", "message": "Auth failed", "user_id": 101}
EOF

{
echo "=== Glob Demo ==="
echo ""

echo "1. Read all JSONL files recursively:"
OUT1=$(jn cat 'test_data/**/*.jsonl' | jq -c '{level, message}')
echo "$OUT1"
echo ""

echo "2. Filter for ERROR level entries:"
OUT2=$(jn cat 'test_data/**/*.jsonl' | jn filter 'select(.level == "ERROR")' | jq -c '{message, user_id}')
echo "$OUT2"
echo ""

echo "3. Count records by level:"
OUT3=$(jn cat 'test_data/**/*.jsonl' | jq -s 'group_by(.level) | map({level: .[0].level, count: length})')
echo "$OUT3"
echo ""

echo "4. Read specific directory pattern:"
OUT4=$(jn cat 'test_data/logs/2024-01/*.jsonl' | jq -c '{timestamp, message}')
echo "$OUT4"
echo ""

echo "=== Done ==="
} > actual.txt

# Cleanup test data
rm -rf test_data

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
