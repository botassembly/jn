#!/bin/bash
# Table Rendering Demo - Pretty-print NDJSON as tables
#
# Demonstrates:
# - Rendering data as ASCII tables (grid, fancy_grid)
# - GitHub-flavored markdown tables
# - Reading tables back to NDJSON (round-trip)
# - Different table formats and styles
# - Column width control and alignment

set -e

echo "=== JN Table Rendering Demo ==="
echo ""

# Sample data for demonstrations
SAMPLE_DATA='{"product":"Widget","price":9.99,"stock":100,"category":"Tools"}
{"product":"Gadget","price":19.99,"stock":50,"category":"Electronics"}
{"product":"Gizmo","price":14.99,"stock":75,"category":"Tools"}
{"product":"Doohickey","price":24.99,"stock":25,"category":"Electronics"}'

# Example 1: Basic grid table (default)
# The grid format uses ASCII box-drawing characters
echo "1. Basic grid table (default format):"
echo "$SAMPLE_DATA" | jn put -- "-~table"
echo ""

# Example 2: Fancy grid with Unicode box characters
# Uses beautiful Unicode box-drawing for terminals that support it
echo "2. Fancy grid with Unicode characters:"
echo "$SAMPLE_DATA" | jn put -- "-~table.fancy_grid"
echo ""

# Example 3: GitHub-flavored markdown
# Perfect for README files and GitHub issues/PRs
echo "3. GitHub markdown table (copy to README.md):"
echo "$SAMPLE_DATA" | jn put -- "-~table.github"
echo ""

# Example 4: Simple format (minimal, clean)
# No borders, just aligned columns
echo "4. Simple format (minimal):"
echo "$SAMPLE_DATA" | jn put -- "-~table.simple"
echo ""

# Example 5: Pipe/markdown format
# Standard markdown table syntax
echo "5. Pipe/markdown format:"
echo "$SAMPLE_DATA" | jn put -- "-~table.pipe"
echo ""

# Example 6: Column width control
# Useful for wide data or narrow terminals
echo "6. With max column width (30 chars):"
echo '{"description":"This is a very long product description that would normally make the table too wide to read comfortably","name":"Product A"}' | jn put -- "-~table?maxcolwidths=30"
echo ""

# Example 7: Reading tables back to NDJSON (round-trip)
# JN can parse tables back to structured data!
echo "7. Round-trip: NDJSON -> table -> NDJSON:"
echo '{"name":"Alice","age":30}
{"name":"Bob","age":25}' > /tmp/sample.json
echo "   Original NDJSON:"
cat /tmp/sample.json
echo ""
echo "   As grid table:"
cat /tmp/sample.json | jn put -- "-~table.grid" | tee /tmp/sample.table
echo ""
echo "   Parsed back to NDJSON:"
cat /tmp/sample.table | jn cat -- "-~table"
echo ""

# Example 8: Reading markdown tables from documentation
echo "8. Parse markdown table to NDJSON:"
MARKDOWN_TABLE='| language | year | creator     |
|----------|------|-------------|
| Python   | 1991 | Guido       |
| Rust     | 2010 | Graydon     |
| Go       | 2009 | Rob Pike    |'
echo "   Input markdown table:"
echo "$MARKDOWN_TABLE"
echo ""
echo "   Parsed as NDJSON:"
echo "$MARKDOWN_TABLE" | jn cat -- "-~table"
echo ""

# Example 9: Pipeline integration - filter then display
echo "9. Pipeline: filter data, then display as table:"
echo "$SAMPLE_DATA" | jn filter 'select(.price > 15)' | jn put -- "-~table.grid"
echo ""

# Example 10: Show different table styles
echo "10. Table style comparison (same data, different formats):"
SMALL_DATA='{"a":1,"b":2}
{"a":3,"b":4}'

echo "    psql style:"
echo "$SMALL_DATA" | jn put -- "-~table?tablefmt=psql"
echo ""
echo "    rst (reStructuredText) style:"
echo "$SMALL_DATA" | jn put -- "-~table?tablefmt=rst"
echo ""
echo "    html style:"
echo "$SMALL_DATA" | jn put -- "-~table?tablefmt=html"
echo ""

# Cleanup
rm -f /tmp/sample.json /tmp/sample.table

echo "=== Demo Complete ==="
echo ""
echo "Key takeaways:"
echo "  - Use '-~table' or '-~table.grid' for terminal output"
echo "  - Use '-~table.github' for markdown documentation"
echo "  - Tables can be parsed back to NDJSON (round-trip support)"
echo "  - Use ?maxcolwidths=N for wide data"
echo "  - Always put tables LAST in pipeline (output is text, not NDJSON)"
