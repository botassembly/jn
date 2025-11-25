# Identify coverage hotspots (large functions with low coverage)
# Parameters: min_lines (default: 50), max_coverage (default: 70)
# Usage: jn cat coverage.lcov | jn filter '@lcov/hotspots?min_lines=50&max_coverage=70'
#
# Output: Large, under-tested functions that should be priority for testing
#         Now uses ACTUAL function size from LCOV (lines field)!
#
# Example:
#   Output: {"file":"resolver.py","function":"plan_execution","lines":112,"coverage":82,"priority":"medium"}

select(.function != "")
| select(.lines >= (($min_lines // "50") | tonumber))
| select(.coverage < (($max_coverage // "70") | tonumber))
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
      elif .coverage < 50 then "high"
      elif .coverage < 70 then "medium"
      else "low"
      end
    )
  }
