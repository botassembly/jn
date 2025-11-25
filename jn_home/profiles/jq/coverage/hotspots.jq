# Identify coverage hotspots (large functions with low coverage)
# Parameters: min_statements (default: 10), max_coverage (default: 70)
# Usage: jn cat coverage.json | jn filter '@coverage/hotspots' -p min_statements=10 -p max_coverage=70
#
# Output: Large, under-tested functions that should be priority for testing
#
# Example:
#   Output: {"file":"resolver.py","function":"plan_execution","statements":52,"coverage":82,"priority":"medium"}
#           {"file":"structure.py","function":"check_dependencies","statements":32,"coverage":55,"priority":"high"}

.files
| to_entries[]
| .key as $file
| .value.functions
| to_entries[]
| select(.key != "")
| select(.value.summary.num_statements >= (($min_statements // "10") | tonumber))
| select(.value.summary.percent_covered < (($max_coverage // "70") | tonumber))
| {
    file: ($file | split("/") | .[-1]),
    function: .key,
    statements: .value.summary.num_statements,
    missing: .value.summary.missing_lines,
    coverage: (.value.summary.percent_covered | floor),
    complexity_score: (.value.summary.num_statements * (100 - .value.summary.percent_covered) / 100 | floor)
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
