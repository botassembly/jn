#!/bin/bash
# Sprint 03 Accuracy Tests

ZQ="$(dirname "$0")/zig-out/bin/zq"
PASS=0
FAIL=0

test_expr() {
    local name="$1"
    local input="$2"
    local expr="$3"
    local expected="$4"

    result=$(echo "$input" | "$ZQ" "$expr" 2>/dev/null)
    if [ "$result" = "$expected" ]; then
        echo "✅ $name"
        ((PASS++))
    else
        echo "❌ $name"
        echo "   Input: $input"
        echo "   Expr:  $expr"
        echo "   Expected: $expected"
        echo "   Got:      $result"
        ((FAIL++))
    fi
}

echo "=== Sprint 03 Accuracy Tests ==="
echo ""
echo "--- Array Functions ---"

test_expr "first" '[1,2,3]' 'first' '1'
test_expr "last" '[1,2,3]' 'last' '3'
test_expr "reverse array" '[1,2,3]' 'reverse' '[3,2,1]'
test_expr "reverse string" '"hello"' 'reverse' '"olleh"'
test_expr "sort" '[3,1,2]' 'sort' '[1,2,3]'
test_expr "unique" '[1,2,2,3,1]' 'unique' '[1,2,3]'
test_expr "flatten" '[[1,2],[3,4]]' 'flatten' '[1,2,3,4]'
test_expr "array construction" '{"a":1,"b":2}' '[.a, .b]' '[1,2]'

echo ""
echo "--- Aggregation Functions ---"

test_expr "add (numbers)" '[1,2,3]' 'add' '6'
test_expr "add (strings)" '["a","b","c"]' 'add' '"abc"'
test_expr "min" '[3,1,2]' 'min' '1'
test_expr "max" '[3,1,2]' 'max' '3'
test_expr "sort_by" '[{"x":3},{"x":1},{"x":2}]' 'sort_by(.x)' '[{"x":1},{"x":2},{"x":3}]'
test_expr "min_by" '[{"x":3},{"x":1},{"x":2}]' 'min_by(.x)' '{"x":1}'
test_expr "max_by" '[{"x":3},{"x":1},{"x":2}]' 'max_by(.x)' '{"x":3}'
test_expr "map" '[1,2,3]' 'map(. * 2)' '[2,4,6]'

echo ""
echo "--- String Functions ---"

test_expr "split" '"a,b,c"' 'split(",")' '["a","b","c"]'
test_expr "join" '["a","b","c"]' 'join(",")' '"a,b,c"'
test_expr "ascii_downcase" '"HELLO"' 'ascii_downcase' '"hello"'
test_expr "ascii_upcase" '"hello"' 'ascii_upcase' '"HELLO"'
test_expr "startswith true" '"hello"' 'startswith("hel")' 'true'
test_expr "startswith false" '"hello"' 'startswith("ell")' 'false'
test_expr "endswith true" '"hello"' 'endswith("llo")' 'true'
test_expr "endswith false" '"hello"' 'endswith("ell")' 'false'
test_expr "contains true" '"hello"' 'contains("ell")' 'true'
test_expr "contains false" '"hello"' 'contains("xyz")' 'false'
test_expr "ltrimstr" '"hello"' 'ltrimstr("hel")' '"lo"'
test_expr "rtrimstr" '"hello"' 'rtrimstr("llo")' '"he"'

echo ""
echo "--- Slurp Mode ---"

result=$(echo -e '1\n2\n3' | "$ZQ" -s 'add')
if [ "$result" = "6" ]; then
    echo "✅ slurp add"
    ((PASS++))
else
    echo "❌ slurp add (got: $result, expected: 6)"
    ((FAIL++))
fi

result=$(echo -e '{"a":1}\n{"a":2}\n{"a":3}' | "$ZQ" -s 'length')
if [ "$result" = "3" ]; then
    echo "✅ slurp length"
    ((PASS++))
else
    echo "❌ slurp length (got: $result, expected: 3)"
    ((FAIL++))
fi

echo ""
echo "--- group_by Test ---"

result=$(echo '[{"type":"a","val":1},{"type":"b","val":2},{"type":"a","val":3}]' | "$ZQ" 'group_by(.type)')
# Check it produces a 2-element outer array
count=$(echo "$result" | jq 'length' 2>/dev/null)
if [ "$count" = "2" ]; then
    echo "✅ group_by (produces 2 groups)"
    ((PASS++))
else
    echo "❌ group_by (got count=$count, expected 2)"
    ((FAIL++))
fi

echo ""
echo "--- unique_by Test ---"

result=$(echo '[{"type":"a","val":1},{"type":"b","val":2},{"type":"a","val":3}]' | "$ZQ" 'unique_by(.type)')
count=$(echo "$result" | jq 'length' 2>/dev/null)
if [ "$count" = "2" ]; then
    echo "✅ unique_by (keeps 2 unique)"
    ((PASS++))
else
    echo "❌ unique_by (got count=$count, expected 2)"
    ((FAIL++))
fi

echo ""
echo "=========================================="
echo "Results: $PASS passed, $FAIL failed"
echo "=========================================="

exit $FAIL
