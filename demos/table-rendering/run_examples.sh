#!/bin/bash
# Table Rendering Demo - Pretty-print NDJSON as tables
#
# Demonstrates the new `jn table` command:
# - Clean syntax: jn table instead of jn put -- "-~table"
# - Multiple formats (grid, fancy_grid, github, simple, etc.)
# - Column width control and alignment options
# - Reading tables back to NDJSON (round-trip)

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
echo "$SAMPLE_DATA" | jn table
echo ""

# Example 2: Fancy grid with Unicode box characters
# Uses beautiful Unicode box-drawing for terminals that support it
echo "2. Fancy grid with Unicode characters:"
echo "$SAMPLE_DATA" | jn table -f fancy_grid
echo ""

# Example 3: GitHub-flavored markdown
# Perfect for README files and GitHub issues/PRs
echo "3. GitHub markdown table (copy to README.md):"
echo "$SAMPLE_DATA" | jn table -f github
echo ""

# Example 4: Simple format (minimal, clean)
# No borders, just aligned columns
echo "4. Simple format (minimal):"
echo "$SAMPLE_DATA" | jn table -f simple
echo ""

# Example 5: Pipe/markdown format
# Standard markdown table syntax
echo "5. Pipe/markdown format:"
echo "$SAMPLE_DATA" | jn table -f pipe
echo ""

# Example 6: Column width control
# Useful for wide data or narrow terminals
echo "6. With max column width (30 chars):"
echo '{"description":"This is a very long product description that would normally make the table too wide to read comfortably","name":"Product A"}' | jn table -w 30
echo ""

# Example 7: Show row index numbers
echo "7. With row index numbers:"
echo "$SAMPLE_DATA" | jn table --index
echo ""

# Example 8: Reading tables back to NDJSON (round-trip)
# JN can parse tables back to structured data!
echo "8. Round-trip: NDJSON -> table -> NDJSON:"
echo '{"name":"Alice","age":30}
{"name":"Bob","age":25}' > /tmp/sample.json
echo "   Original NDJSON:"
cat /tmp/sample.json
echo ""
echo "   As grid table:"
cat /tmp/sample.json | jn table | tee /tmp/sample.table
echo ""
echo "   Parsed back to NDJSON:"
cat /tmp/sample.table | jn cat -- "-~table"
echo ""

# Example 9: Reading markdown tables from documentation
echo "9. Parse markdown table to NDJSON:"
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

# Example 10: Pipeline integration - filter then display
echo "10. Pipeline: filter data, then display as table:"
echo "$SAMPLE_DATA" | jn filter 'select(.price > 15)' | jn table
echo ""

# Example 11: Show different table styles
echo "11. Table style comparison (same data, different formats):"
SMALL_DATA='{"a":1,"b":2}
{"a":3,"b":4}'

echo "    psql style:"
echo "$SMALL_DATA" | jn table -f psql
echo ""
echo "    rst (reStructuredText) style:"
echo "$SMALL_DATA" | jn table -f rst
echo ""
echo "    html style:"
echo "$SMALL_DATA" | jn table -f html
echo ""

# Cleanup
rm -f /tmp/sample.json /tmp/sample.table

echo "=== Demo Complete ==="
echo ""
echo "Key takeaways:"
echo "  - Use 'jn table' for terminal output (clean syntax!)"
echo "  - Use 'jn table -f github' for markdown documentation"
echo "  - Use 'jn table -w N' to limit column width"
echo "  - Use 'jn table --index' for row numbers"
echo "  - Tables can be parsed back to NDJSON with 'jn cat -~table'"
echo "  - Always put tables LAST in pipeline (output is text, not NDJSON)"
