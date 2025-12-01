# Add coverage range to each file
# Usage: jn cat coverage.lcov | jn filter '@lcov/files-by-coverage' | jq -s 'group_by(.range) | ...'
#
# Output: Each file with its coverage range
#
# Example:
#   Output: {"file":"parser.py","coverage":89,"range":"80-100%"}
#
# For summary, pipe to: jq -s 'group_by(.range) | map({range: .[0].range, files: map(.file) | unique, count: length})'

# Tag each file with its coverage range
{
  file: .filename,
  full_path: .file,
  coverage: (.coverage | floor),
  range: (
    if .coverage < 20 then "0-20%"
    else (if .coverage < 40 then "20-40%"
    else (if .coverage < 60 then "40-60%"
    else (if .coverage < 80 then "60-80%"
    else "80-100%"
    end) end) end) end
  )
}
# Note: This outputs one record per function. To get per-file stats,
# you'll need to aggregate externally with jq -s
