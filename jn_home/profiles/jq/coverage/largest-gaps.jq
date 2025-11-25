# Find functions with the most missing lines
# Parameters: min_missing (default: 5)
# Usage: jn cat coverage.json | jn filter '@coverage/largest-gaps' -p min_missing=5
#
# Output: Functions sorted by number of missing lines (most uncovered code)
#
# Example:
#   Output: {"file":"resolver.py","function":"_resolve_url_and_headers","missing":16,"coverage":58}
#           {"file":"structure.py","function":"check_dependencies","missing":14,"coverage":55}

.files
| to_entries[]
| .key as $file
| .value.functions
| to_entries[]
| select(.key != "")
| select(.value.summary.missing_lines >= (($min_missing // "5") | tonumber))
| {
    file: ($file | split("/") | .[-1]),
    function: .key,
    missing: .value.summary.missing_lines,
    statements: .value.summary.num_statements,
    coverage: (.value.summary.percent_covered | floor)
  }
| . + {uncovered_pct: ((.missing * 100 / .statements) | floor)}
