#!/bin/bash
# Adapter & Merge Demo - Unified Data Orchestration
#
# Demonstrates:
# - SQL optional parameters with DuckDB (pushdown adapters)
# - JQ profile string substitution (streaming adapters)
# - jn merge for comparative analysis (composability)

set -e

DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DEMO_DIR"

echo "=== JN Adapter & Merge Demo ==="
echo ""

# Setup: Create test database (PEP 723 script with uv shebang)
echo "Setting up test data..."
./setup_data.py
echo ""

# Export JN_HOME to use demo profiles
export JN_HOME="$DEMO_DIR"

# =============================================================================
# PART 1: SQL Optional Parameters (Pushdown Adapters)
# =============================================================================
echo "═══════════════════════════════════════════════════════════════"
echo "PART 1: SQL Optional Parameters (Pushdown Adapters)"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "The DuckDB profile uses the optional parameter pattern:"
echo "  (\$param IS NULL OR column = \$param)"
echo ""
echo "This allows a single query to handle multiple filter scenarios."
echo ""

echo "1. Query ALL treatments (no filters):"
echo "   jn cat @genie/treatment"
jn cat @genie/treatment | jn head -n 5
echo "   ... showing first 5 of all records"
echo ""

echo "2. Query FOLFOX regimen only:"
echo "   jn cat '@genie/treatment?regimen=FOLFOX'"
jn cat "@genie/treatment?regimen=FOLFOX"
echo ""

echo "3. Query high survivors (os_months >= 20):"
echo "   jn cat '@genie/treatment?min_survival=20'"
jn cat "@genie/treatment?min_survival=20"
echo ""

echo "4. Combined filters (FOLFIRI + min 15 months survival):"
echo "   jn cat '@genie/treatment?regimen=FOLFIRI&min_survival=15'"
jn cat "@genie/treatment?regimen=FOLFIRI&min_survival=15"
echo ""

# =============================================================================
# PART 2: Merge Command (Composability)
# =============================================================================
echo "═══════════════════════════════════════════════════════════════"
echo "PART 2: Merge Command (Composability)"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "The merge command combines multiple sources into a single stream"
echo "with metadata injection (_label, _source)."
echo ""

echo "1. Compare East vs West sales:"
echo "   jn merge 'sales.csv?region=East:label=East' 'sales.csv?region=West:label=West'"
echo ""
echo "   Note: CSV filtering requires jn filter, but merge labels all records."
echo "   For filtered comparison, use this pattern:"
echo ""
jn cat sales.csv | jn filter 'select(.region == "East")' > /tmp/east.json
jn cat sales.csv | jn filter 'select(.region == "West")' > /tmp/west.json
echo "   jn merge '/tmp/east.json:label=East' '/tmp/west.json:label=West'"
jn merge "/tmp/east.json:label=East" "/tmp/west.json:label=West"
echo ""

echo "2. Compare treatment regimens from database:"
echo "   Using DuckDB optional params with merge for cohort comparison..."
jn cat "@genie/treatment?regimen=FOLFOX" | jn put /tmp/folfox.jsonl
jn cat "@genie/treatment?regimen=FOLFIRI" | jn put /tmp/folfiri.jsonl
echo "   jn merge '/tmp/folfox.jsonl:label=FOLFOX' '/tmp/folfiri.jsonl:label=FOLFIRI'"
jn merge "/tmp/folfox.jsonl:label=FOLFOX" "/tmp/folfiri.jsonl:label=FOLFIRI"
echo ""

echo "3. Use merged data for analysis:"
echo "   Count by label to compare cohort sizes:"
jn merge "/tmp/folfox.jsonl:label=FOLFOX" "/tmp/folfiri.jsonl:label=FOLFIRI" | \
  jq -s 'group_by(._label) | map({label: .[0]._label, count: length})'
echo ""

# Cleanup
rm -f /tmp/east.json /tmp/west.json /tmp/folfox.jsonl /tmp/folfiri.jsonl

echo "═══════════════════════════════════════════════════════════════"
echo "Demo Complete!"
echo ""
echo "Key Takeaways:"
echo "  - SQL optional params: Use (\$param IS NULL OR col = \$param)"
echo "  - Merge command: Combine sources with :label=X for analysis"
echo "  - Profile resolution: @namespace/query works for DuckDB profiles"
echo "═══════════════════════════════════════════════════════════════"
