#!/bin/bash
# JN Filter Functions Demo - Data Transformation Functions
set -e
cd "$(dirname "$0")"

rm -f actual.txt

echo "=== JN Filter Functions Demo ===" >> actual.txt
echo "" >> actual.txt

echo "1. Object transforms (keys, values):" >> actual.txt
echo '{"name":"Alice","age":30}' | jn filter 'keys' >> actual.txt
echo '{"name":"Alice","age":30}' | jn filter 'values' >> actual.txt
echo "" >> actual.txt

echo "2. Array operations (unique, sort, reverse):" >> actual.txt
echo '[3,1,4,1,5,9,2,6]' | jn filter 'unique' >> actual.txt
echo '[3,1,4,1,5,9,2,6]' | jn filter 'sort' >> actual.txt
echo '[1,2,3,4,5]' | jn filter 'reverse' >> actual.txt
echo "" >> actual.txt

echo "3. String functions:" >> actual.txt
echo '{"text":"hello world"}' | jn filter -r '.text | ascii_upcase' >> actual.txt
echo '{"text":"  hello  "}' | jn filter -r '.text | trim' >> actual.txt
echo '{"csv":"a,b,c"}' | jn filter -r '.csv | split(",")' >> actual.txt
echo "" >> actual.txt

echo "4. Math functions:" >> actual.txt
echo '{"x":-42}' | jn filter -r '.x | abs' >> actual.txt
echo '{"x":16}' | jn filter -r '.x | sqrt' >> actual.txt
echo '{"x":3.7}' | jn filter -r '.x | floor' >> actual.txt
echo '{"x":3.2}' | jn filter -r '.x | ceil' >> actual.txt
echo "" >> actual.txt

echo "5. Case conversion:" >> actual.txt
echo '{"name":"HelloWorld"}' | jn filter -r '.name | snakecase' >> actual.txt
echo '{"name":"hello_world"}' | jn filter -r '.name | camelcase' >> actual.txt
echo '{"name":"hello_world"}' | jn filter -r '.name | pascalcase' >> actual.txt
echo "" >> actual.txt

echo "6. Flatten and length:" >> actual.txt
echo '[[1,2],[3,[4,5]]]' | jn filter 'flatten' >> actual.txt
echo '[1,2,3,4,5]' | jn filter 'length' >> actual.txt
echo "" >> actual.txt

echo "7. First and last:" >> actual.txt
echo '[10,20,30]' | jn filter 'first' >> actual.txt
echo '[10,20,30]' | jn filter 'last' >> actual.txt
echo "" >> actual.txt

echo "8. Chaining functions:" >> actual.txt
echo '{"name":"  HELLO world  "}' | jn filter -r '.name | trim | ascii_downcase | split(" ") | reverse | join("-")' >> actual.txt
echo "" >> actual.txt

echo "=== Done ===" >> actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
