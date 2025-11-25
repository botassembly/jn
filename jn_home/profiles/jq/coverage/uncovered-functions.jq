# Find functions with 0% coverage
# Usage: jn cat coverage.json | jn filter '@coverage/uncovered-functions'
#
# Output: List of functions with zero coverage including file, function name, and line count
#
# Example:
#   Input:  coverage.json (single record with .files)
#   Output: {"file":"types.py","function":"ResolvedAddress.__str__","statements":6}
#           {"file":"report.py","function":"format_json","statements":10}

.files
| to_entries[]
| .key as $file
| .value.functions
| to_entries[]
| select(.value.summary.percent_covered == 0)
| select(.key != "")
| {
    file: ($file | split("/") | .[-1]),
    function: .key,
    statements: .value.summary.num_statements,
    missing_lines: .value.summary.missing_lines
  }
