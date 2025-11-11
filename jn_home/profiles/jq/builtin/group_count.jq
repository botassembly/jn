# Count occurrences by key
# Parameters: by (group key)
# Usage: jn cat data.json | jn filter '@builtin/group_count' --by status
#
# Example:
#   Input:  {"status":"active"} (NDJSON - one per line)
#           {"status":"inactive"}
#           {"status":"active"}
#   Output: {"status":"active","count":2}
#           {"status":"inactive","count":1}

# Slurp NDJSON lines into array, then group
# Use '. as $first | [$first] + [inputs]' to include the first record
. as $first | [$first] + [inputs] | group_by(.[$by]) | map({
  ($by): .[0][$by],
  count: length
}) | .[]
