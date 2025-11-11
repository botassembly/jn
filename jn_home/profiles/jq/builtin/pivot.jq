# Pivot table: Convert NDJSON stream to pivoted structure
# Parameters: row_key, col_key, value_key
# Usage: jn cat data.json | jn filter '@builtin/pivot' --row product --col month --value revenue
#
# Example:
#   Input:  {"product":"A","month":"Jan","revenue":100} (NDJSON - one per line)
#           {"product":"A","month":"Feb","revenue":150}
#   Output: {"A": {"Jan": 100, "Feb": 150}}

# Slurp NDJSON lines into array, then pivot
# Use '. as $first | [$first] + [inputs]' to include the first record
. as $first | [$first] + [inputs] | group_by(.[$row_key]) | map({
  key: .[0][$row_key],
  values: group_by(.[$col_key]) | map({
    key: .[0][$col_key],
    value: map(.[$value_key]) | add
  }) | from_entries
}) | from_entries
