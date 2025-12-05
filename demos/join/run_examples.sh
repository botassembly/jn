#!/bin/bash
# Join Demo - Stream Enrichment via Hash Join

set -e

DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$DEMO_DIR/../.." && pwd)"
cd "$DEMO_DIR"

# Ensure JN_HOME is set for finding tools
export JN_HOME="${JN_HOME:-$REPO_ROOT}"
export PATH="$REPO_ROOT/tools/zig/jn/bin:$PATH"

echo "=== JN Join Demo ==="
echo ""

# Create test data
echo "Setting up test data..."
cat > customers.csv << 'EOF'
id,name,state
1,Alice,NY
2,Bob,CA
3,Charlie,TX
EOF

cat > orders.csv << 'EOF'
order_id,customer_id,amount,product
O1,1,100,Widget
O2,1,200,Gadget
O3,2,150,Widget
EOF

echo "customers.csv:"
cat customers.csv
echo ""
echo "orders.csv:"
cat orders.csv
echo ""

# =============================================================================
# PART 1: Basic Left Join
# =============================================================================
echo "═══════════════════════════════════════════════════════════════"
echo "PART 1: Basic Left Join"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Enrich customers with their orders:"
echo "  jn cat customers.csv | jn join orders.csv \\"
echo "    --left-key id --right-key customer_id --target orders"
echo ""
jn cat customers.csv | jn join orders.csv \
  --left-key id --right-key customer_id --target orders
echo ""
echo "Note: Alice has 2 orders, Bob has 1, Charlie has 0 (empty array)."
echo ""

# =============================================================================
# PART 2: Inner Join
# =============================================================================
echo "═══════════════════════════════════════════════════════════════"
echo "PART 2: Inner Join (only customers with orders)"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  jn cat customers.csv | jn join orders.csv \\"
echo "    --left-key id --right-key customer_id --target orders --inner"
echo ""
jn cat customers.csv | jn join orders.csv \
  --left-key id --right-key customer_id --target orders --inner
echo ""
echo "Note: Charlie is filtered out (no orders)."
echo ""

# =============================================================================
# PART 3: Field Selection with --pick
# =============================================================================
echo "═══════════════════════════════════════════════════════════════"
echo "PART 3: Field Selection (--pick)"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Only include specific fields from orders:"
echo "  jn cat customers.csv | jn join orders.csv \\"
echo "    --left-key id --right-key customer_id --target orders \\"
echo "    --pick order_id --pick amount"
echo ""
jn cat customers.csv | jn join orders.csv \
  --left-key id --right-key customer_id --target orders \
  --pick order_id --pick amount
echo ""
echo "Note: Only order_id and amount in nested objects (no product, customer_id)."
echo ""

# =============================================================================
# PART 4: Chaining with Filter
# =============================================================================
echo "═══════════════════════════════════════════════════════════════"
echo "PART 4: Chaining with jn filter"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Find customers with more than 1 order:"
echo "  jn cat customers.csv | jn join orders.csv \\"
echo "    --left-key id --right-key customer_id --target orders \\"
echo "    | jn filter 'select((.orders | length) > 1)'"
echo ""
jn cat customers.csv | jn join orders.csv \
  --left-key id --right-key customer_id --target orders \
  | jn filter 'select((.orders | length) > 1)'
echo ""

# Cleanup
rm -f customers.csv orders.csv

echo "═══════════════════════════════════════════════════════════════"
echo "Demo Complete!"
echo ""
echo "Key Takeaways:"
echo "  - Left join (default): All left records kept, empty array if no match"
echo "  - Inner join (--inner): Only records with matches"
echo "  - Field selection (--pick): Include only specific fields from right"
echo "  - Condensation: Multiple matches become arrays, not row explosions"
echo "═══════════════════════════════════════════════════════════════"
