#!/bin/bash
# GenomOncology API Demo Examples

echo "=== GenomOncology API Demo ==="
echo ""

# Check if environment variables are set
if [ -z "$GENOMONCOLOGY_URL" ] || [ -z "$GENOMONCOLOGY_API_KEY" ]; then
    echo "ERROR: Required environment variables not set"
    echo ""
    echo "Please set:"
    echo "  export GENOMONCOLOGY_URL='your-org.genomoncology.com'"
    echo "  export GENOMONCOLOGY_API_KEY='your-api-key'"
    echo ""
    exit 1
fi

echo "Environment configured:"
echo "  URL: $GENOMONCOLOGY_URL"
echo "  API Key: ${GENOMONCOLOGY_API_KEY:0:10}..."
echo ""

echo "Example queries (not executed, copy/paste to run):"
echo ""

echo "1. Query BRAF alterations:"
echo "   jn cat @genomoncology/alterations?gene=BRAF&limit=5"
echo ""

echo "2. Search clinical trials for EGFR:"
echo "   jn cat @genomoncology/clinical_trials?gene=EGFR&limit=5"
echo ""

echo "3. Get gene information:"
echo "   jn cat @genomoncology/genes?symbol=TP53"
echo ""

echo "4. Pipeline: Filter Phase 3 trials:"
echo "   jn cat @genomoncology/clinical_trials?gene=BRAF | jn filter '.phase == \"Phase 3\"' | jn put phase3.json"
echo ""

echo "See README.md for more examples and setup instructions"
