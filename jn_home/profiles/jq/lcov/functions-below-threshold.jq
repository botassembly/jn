# Find functions below a coverage threshold
# Parameters: threshold (required, numeric - e.g., 80)
# Usage: jn cat coverage.lcov | jn filter '@lcov/functions-below-threshold?threshold=80'
#
# Output: Functions with coverage below the specified threshold
#
# Example:
#   Output: {"file":"parser.py","function":"_validate_address","coverage":70,"lines":67,"missing":9}

select(.function | length > 0)
| select(.coverage < $threshold)
| {
    file: .filename,
    function: .function,
    coverage: (.coverage | floor),
    lines: .lines,
    total_lines: .total_lines,
    missing_lines: .missing_lines,
    branches: .total_branches,
    branch_coverage: (.branch_coverage | floor)
  }
