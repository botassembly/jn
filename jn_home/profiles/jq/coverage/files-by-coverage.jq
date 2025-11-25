# Group files by coverage percentage ranges
# Usage: jn cat coverage.json | jn filter '@coverage/files-by-coverage'
#
# Output: Files grouped into coverage buckets (0-20%, 20-40%, 40-60%, 60-80%, 80-100%)
#
# Example:
#   Output: {"range":"80-100%","files":["parser.py","resolver.py"],"count":2}
#           {"range":"60-80%","files":["service.py"],"count":1}

.files
| to_entries
| map({
    file: (.key | split("/") | .[-1]),
    coverage: .value.summary.percent_covered
  })
| group_by(
    if .coverage >= 80 then "80-100%"
    elif .coverage >= 60 then "60-80%"
    elif .coverage >= 40 then "40-60%"
    elif .coverage >= 20 then "20-40%"
    else "0-20%"
    end
  )
| map({
    range: .[0].coverage | (
      if . >= 80 then "80-100%"
      elif . >= 60 then "60-80%"
      elif . >= 40 then "40-60%"
      elif . >= 20 then "20-40%"
      else "0-20%"
      end
    ),
    files: map(.file),
    count: length,
    avg_coverage: (map(.coverage) | add / length | floor)
  })
| sort_by(.range) | reverse | .[]
