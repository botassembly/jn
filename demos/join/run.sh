#!/bin/bash
# Join Demo - Stream Enrichment via Hash Join
set -e
cd "$(dirname "$0")"

rm -f actual.txt

echo "=== Join Demo ===" >> actual.txt
echo "" >> actual.txt

echo "1. Left Join (enrich customers with orders):" >> actual.txt
jn cat customers.csv | jn join orders.csv \
  --left-key=id --right-key=customer_id | jn filter '.' >> actual.txt
echo "" >> actual.txt

echo "2. Inner Join (only customers with orders):" >> actual.txt
jn cat customers.csv | jn join orders.csv \
  --left-key=id --right-key=customer_id --inner | jn filter '.' >> actual.txt
echo "" >> actual.txt

echo "3. Chain with filter (high value orders >150):" >> actual.txt
jn cat customers.csv | jn join orders.csv \
  --left-key=id --right-key=customer_id \
  | jn filter 'select((.amount | tonumber) > 150)' >> actual.txt
echo "" >> actual.txt

echo "4. Select specific fields after join:" >> actual.txt
jn cat customers.csv | jn join orders.csv \
  --left-key=id --right-key=customer_id \
  | jn filter '{customer: .name, order: .order_id, amount}' >> actual.txt
echo "" >> actual.txt

echo "=== Done ===" >> actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
