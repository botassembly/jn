#!/bin/bash
# Join Demo - Stream Enrichment via Hash Join
set -e
cd "$(dirname "$0")"

{
echo "=== Join Demo ==="
echo ""

echo "1. Left Join (enrich customers with orders):"
jn cat customers.csv | jn join orders.csv \
  --left-key=id --right-key=customer_id | jq -c '.'
echo ""

echo "2. Inner Join (only customers with orders):"
jn cat customers.csv | jn join orders.csv \
  --left-key=id --right-key=customer_id --inner | jq -c '.'
echo ""

echo "3. Chain with filter (high value orders >150):"
jn cat customers.csv | jn join orders.csv \
  --left-key=id --right-key=customer_id \
  | jn filter 'select((.amount | tonumber) > 150)' | jq -c '.'
echo ""

echo "4. Select specific fields after join:"
jn cat customers.csv | jn join orders.csv \
  --left-key=id --right-key=customer_id \
  | jq -c '{customer: .name, order: .order_id, amount}'
echo ""

echo "=== Done ==="
} > actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
