# Find functions with poor branch coverage
# Parameters: threshold (default: 70)
# Usage: jn cat coverage.json | jn filter '@coverage/poor-branch-coverage' -p threshold=70
#
# Output: Functions with branches but low branch coverage percentage
#
# Example:
#   Output: {"file":"parser.py","function":"_validate_address","branch_coverage":50,"branches":10,"covered":5}

.files
| to_entries[]
| .key as $file
| .value.functions
| to_entries[]
| select(.key != "")
| select(.value.summary.num_branches > 0)
| {
    file: ($file | split("/") | .[-1]),
    function: .key,
    branches: .value.summary.num_branches,
    covered: .value.summary.covered_branches,
    branch_coverage: (
      if .value.summary.num_branches > 0
      then (.value.summary.covered_branches * 100.0 / .value.summary.num_branches | floor)
      else 100
      end
    )
  }
| select(.branch_coverage < (($threshold // "70") | tonumber))
| . + {partial_branches: (.branches - .covered)}
