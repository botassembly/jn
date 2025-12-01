# Tag each function with its module (for aggregation)
# Usage: jn cat coverage.lcov | jn filter '@lcov/summary-by-module' | jq -s 'group_by(.module) | ...'
#
# Output: Each function tagged with module
#
# Example:
#   Output: {"module":"src/jn/core","file":"pipeline.py","function":"convert","coverage":95}
#
# For aggregated summary, pipe to:
# jq -s 'group_by(.module) | map({module: .[0].module, functions: length,
#        coverage: ((map(.executed_lines)|add)*100/(map(.total_lines)|add)|floor)})'

# Extract module from file path and include key stats
{
  module: ((.file | split("/")) | .[:-1] | join("/")),
  file: .filename,
  function: .function,
  total_lines: .total_lines,
  executed_lines: .executed_lines,
  coverage: (.coverage | floor),
  total_branches: .total_branches,
  taken_branches: .taken_branches,
  branch_coverage: (.branch_coverage | floor)
}
# Note: This outputs one record per function. Aggregate with jq -s for module summaries
