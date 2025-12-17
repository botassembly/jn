#!/bin/bash
# Code Analysis Demo - Using @code/ profiles
set -e
cd "$(dirname "$0")"

# Run from project root for consistent paths
PROJECT_ROOT="$(cd "../.." && pwd)"
cd "$PROJECT_ROOT"

{
echo "=== Code Analysis Demo ==="
echo ""

echo "1. List code files (first 5):"
OUT1=$(jn cat @code/files | jn head --lines=5 | jn filter '.')
echo "$OUT1"
echo ""

echo "2. Count Python files:"
OUT2=$(jn cat @code/files | jn filter 'select(.file | endswith(".py"))' | jn filter -s 'length')
echo "$OUT2"
echo ""

echo "3. Count Zig files:"
OUT3=$(jn cat @code/files | jn filter 'select(.file | endswith(".zig"))' | jn filter -s 'length')
echo "$OUT3"
echo ""

echo "=== Done ==="
} > "$OLDPWD/actual.txt"

cd "$OLDPWD"

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
