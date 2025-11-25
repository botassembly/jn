# Find functions below a coverage threshold
# Parameters: threshold (default: 80)
# Usage: jn cat coverage.json | jn filter '@coverage/functions-below-threshold' -p threshold=80
#
# Output: Functions with coverage below the specified threshold
#
# Example:
#   Input:  coverage.json
#   Output: {"file":"parser.py","function":"_validate_address","coverage":70,"statements":30,"missing":9}

.files
| to_entries[]
| .key as $file
| .value.functions
| to_entries[]
| select(.key != "")
| select(.value.summary.percent_covered < (($threshold // "80") | tonumber))
| {
    file: ($file | split("/") | .[-1]),
    function: .key,
    coverage: (.value.summary.percent_covered | floor),
    statements: .value.summary.num_statements,
    missing: .value.summary.missing_lines,
    branches: .value.summary.num_branches
  }
