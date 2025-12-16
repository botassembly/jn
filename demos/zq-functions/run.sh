#!/bin/bash
# ZQ Functions Demo - Data Transformation Functions
set -e
cd "$(dirname "$0")"

rm -f actual.txt

echo "=== ZQ Functions Demo ===" >> actual.txt
echo "" >> actual.txt

echo "1. Object transforms (keys, values):" >> actual.txt
echo '{"name":"Alice","age":30}' | zq 'keys' >> actual.txt
echo '{"name":"Alice","age":30}' | zq 'values' >> actual.txt
echo "" >> actual.txt

echo "2. Array operations (unique, sort, reverse):" >> actual.txt
echo '[3,1,4,1,5,9,2,6]' | zq 'unique' >> actual.txt
echo '[3,1,4,1,5,9,2,6]' | zq 'sort' >> actual.txt
echo '[1,2,3,4,5]' | zq 'reverse' >> actual.txt
echo "" >> actual.txt

echo "3. String functions:" >> actual.txt
echo '{"text":"hello world"}' | zq -r '.text | ascii_upcase' >> actual.txt
echo '{"text":"  hello  "}' | zq -r '.text | trim' >> actual.txt
echo '{"csv":"a,b,c"}' | zq -r '.csv | split(",")' >> actual.txt
echo "" >> actual.txt

echo "4. Math functions:" >> actual.txt
echo '{"x":-42}' | zq -r '.x | abs' >> actual.txt
echo '{"x":16}' | zq -r '.x | sqrt' >> actual.txt
echo '{"x":3.7}' | zq -r '.x | floor' >> actual.txt
echo '{"x":3.2}' | zq -r '.x | ceil' >> actual.txt
echo "" >> actual.txt

echo "5. Case conversion:" >> actual.txt
echo '{"name":"HelloWorld"}' | zq -r '.name | snakecase' >> actual.txt
echo '{"name":"hello_world"}' | zq -r '.name | camelcase' >> actual.txt
echo '{"name":"hello_world"}' | zq -r '.name | pascalcase' >> actual.txt
echo "" >> actual.txt

echo "6. Flatten and length:" >> actual.txt
echo '[[1,2],[3,[4,5]]]' | zq 'flatten' >> actual.txt
echo '[1,2,3,4,5]' | zq 'length' >> actual.txt
echo "" >> actual.txt

echo "7. First and last:" >> actual.txt
echo '[10,20,30]' | zq 'first' >> actual.txt
echo '[10,20,30]' | zq 'last' >> actual.txt
echo "" >> actual.txt

echo "8. Chaining functions:" >> actual.txt
echo '{"name":"  HELLO world  "}' | zq -r '.name | trim | ascii_downcase | split(" ") | reverse | join("-")' >> actual.txt
echo "" >> actual.txt

echo "=== Done ===" >> actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
