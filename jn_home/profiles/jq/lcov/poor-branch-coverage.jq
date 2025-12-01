# Find functions with poor branch coverage
# Parameters: threshold (required, numeric - e.g., 70)
# Usage: jn cat coverage.lcov | jn filter '@lcov/poor-branch-coverage?threshold=70'
#
# Output: Functions with branches but low branch coverage percentage
#
# Example:
#   Output: {"file":"parser.py","function":"_validate_address","branch_coverage":50,"branches":10,"taken":5}

select(.function | length > 0)
| select(.total_branches > 0)
| select(.branch_coverage < $threshold)
| {
    file: .filename,
    function: .function,
    branches: .total_branches,
    taken: .taken_branches,
    branch_coverage: (.branch_coverage | floor),
    partial_branches: .partial_branches
  }
