# Find functions with the most missing lines
# Parameters: min_missing (required, numeric - e.g., 5)
# Usage: jn cat coverage.lcov | jn filter '@lcov/largest-gaps?min_missing=5'
#
# Output: Functions sorted by number of missing lines (most uncovered code)
#
# Example:
#   Output: {"file":"resolver.py","function":"_resolve_url_and_headers","missing":16,"lines":38,"coverage":58}

select(.function | length > 0)
| select(.missing_lines >= $min_missing)
| {
    file: .filename,
    function: .function,
    missing: .missing_lines,
    lines: .lines,
    total_lines: .total_lines,
    coverage: (.coverage | floor),
    uncovered_pct: ((.missing_lines * 100 / .total_lines) | floor)
  }
