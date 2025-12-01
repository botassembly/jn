# Find functions with 0% coverage
# Usage: jn cat coverage.lcov | jn filter '@lcov/uncovered-functions'
#
# Output: Functions that have never been executed
#
# Example:
#   Output: {"file":"types.py","function":"ResolvedAddress.__str__","lines":6,"missing_lines":6}

select(.coverage == 0)
| select(.function | length > 0)
| {
    file: .filename,
    function: .function,
    lines: .lines,
    start_line: .start_line,
    end_line: .end_line,
    total_lines: .total_lines,
    missing_lines: .missing_lines
  }
