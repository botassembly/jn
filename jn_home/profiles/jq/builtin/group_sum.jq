# Group by key and sum values
# Parameters: by (group key), sum (field to sum)
# Usage: jn cat data.json | jn filter '@builtin/group_sum' -p by=customer -p sum=total
#
# Example:
#   Input:  {"customer":"Alice","total":100} (NDJSON - one per line)
#           {"customer":"Alice","total":50}
#           {"customer":"Bob","total":75}
#   Output: {"customer":"Alice","total":150}
#           {"customer":"Bob","total":75}

# Slurp NDJSON lines into array, then group
# Use '. as $first | [$first] + [inputs]' to include the first record
. as $first | [$first] + [inputs] | group_by(.[$by]) | map({
  ($by): .[0][$by],
  ($sum): map(.[$sum]) | add
}) | .[]
