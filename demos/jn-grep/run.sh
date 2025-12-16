#!/bin/bash
# JN Grep Demo - Line-based Text Filtering with NDJSON
set -e
cd "$(dirname "$0")"

# Create deterministic test data
mkdir -p test_data
cat > test_data/app.log << 'EOF'
2024-12-15 10:00:01 INFO Starting application
2024-12-15 10:00:02 DEBUG Loading configuration
2024-12-15 10:00:03 INFO Database connected
2024-12-15 10:00:05 WARN High memory usage detected
2024-12-15 10:00:10 ERROR Failed to connect to cache
2024-12-15 10:00:11 INFO Retrying connection
2024-12-15 10:00:15 ERROR Cache connection timeout
2024-12-15 10:00:20 INFO Application ready
EOF

cat > test_data/users.txt << 'EOF'
alice:1001:Engineering:alice@example.com
bob:1002:Marketing:bob@example.com
charlie:1003:Engineering:charlie@example.com
diana:1004:Sales:diana@example.com
EOF

rm -f actual.txt

echo "=== JN Grep Demo ===" >> actual.txt
echo "" >> actual.txt

echo "1. Convert text to NDJSON with line numbers:" >> actual.txt
jn-sh --raw cat test_data/app.log | head -3 >> actual.txt
echo "" >> actual.txt

echo "2. Search for ERROR lines:" >> actual.txt
jn-sh --raw cat test_data/app.log | zq 'select(.text | contains("ERROR"))' >> actual.txt
echo "" >> actual.txt

echo "3. Get line numbers of errors:" >> actual.txt
jn-sh --raw cat test_data/app.log | zq -r 'select(.text | contains("ERROR")) | .line' >> actual.txt
echo "" >> actual.txt

echo "4. Lines NOT containing DEBUG:" >> actual.txt
jn-sh --raw cat test_data/app.log | zq 'select(not (.text | contains("DEBUG")))' >> actual.txt
echo "" >> actual.txt

echo "5. Parse colon-delimited file:" >> actual.txt
jn-sh --raw cat test_data/users.txt | zq '{line, user: (.text | split(":") | first), dept: (.text | split(":") | .[2])}' >> actual.txt
echo "" >> actual.txt

echo "6. Count lines matching pattern:" >> actual.txt
jn-sh --raw cat test_data/app.log | zq 'select(.text | contains("ERROR"))' | zq -s 'length' >> actual.txt
echo "" >> actual.txt

echo "=== Done ===" >> actual.txt

# Cleanup
rm -rf test_data

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
