# Identify coverage hotspots (large functions with low coverage)
# Parameters: min_lines (required, numeric), max_coverage (required, numeric)
# Usage: jn cat coverage.lcov | jn filter '@lcov/hotspots?min_lines=50&max_coverage=70'
#
# Output: Large, under-tested functions that should be priority for testing
#         Now uses ACTUAL function size from LCOV (lines field)!
#
# Example:
#   Output: {"file":"resolver.py","function":"plan_execution","lines":112,"coverage":82,"priority":"medium"}

select(.function | length > 0)
| select(.lines >= $min_lines)
| select(.coverage < $max_coverage)
| {
    file: .filename,
    function: .function,
    lines: .lines,
    start_line: .start_line,
    end_line: .end_line,
    missing: .missing_lines,
    coverage: (.coverage | floor),
    complexity_score: (.lines * (100 - .coverage) / 100 | floor)
  }
| . + {
    priority: (
      if .coverage < 30 then "critical"
      else (if .coverage < 50 then "high"
      else (if .coverage < 70 then "medium"
      else "low"
      end) end) end
    )
  }
