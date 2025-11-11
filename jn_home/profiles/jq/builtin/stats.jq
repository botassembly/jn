# Basic statistics: min, max, avg, sum, count
# Parameters: field (field to calculate stats for)
# Usage: jn cat data.json | jn filter '@builtin/stats' -p field=revenue
#
# Example:
#   Input:  {"revenue":100} (NDJSON - one per line)
#           {"revenue":150}
#           {"revenue":200}
#   Output: {"min":100,"max":200,"avg":150,"sum":450,"count":3}

# Slurp NDJSON lines into array, extract field values, calculate stats
# Use '. as $first | [$first] + [inputs]' to include the first record
. as $first | [$first] + [inputs] | map(.[$field]) | {
  min: min,
  max: max,
  avg: (add / length),
  sum: add,
  count: length
}
