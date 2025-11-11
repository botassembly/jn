# Pivot annotations by transcript
# Takes annotation records with nested transcript arrays and yields one record per transcript
# Each transcript has coding (c.) and protein (p.) nomenclature (NM_/NP_ combos)
#
# Usage: jn cat @genomoncology/annotations | jn filter '@genomoncology/by_transcript'
#
# Example:
#   Input:  {"gene":"BRAF", "transcripts":[{"nm":"NM_004333", "np":"NP_004324", "c":"c.1799T>A", "p":"p.V600E"}, ...]}
#   Output: {"gene":"BRAF", "nm":"NM_004333", "np":"NP_004324", "c":"c.1799T>A", "p":"p.V600E"}
#           {"gene":"BRAF", "nm":"NM_001354609", "np":"NP_001341538", "c":"c.1799T>A", "p":"p.V600E"}
#           ... (one record per transcript)

# Check if transcripts field exists and is an array
if .transcripts and (.transcripts | type == "array") and (.transcripts | length > 0) then
  # Capture common fields
  . as $parent |
  # Explode transcripts array into individual records
  .transcripts[] |
  # Merge parent fields with transcript fields
  $parent + . |
  # Remove the original transcripts array
  del(.transcripts)
else
  # No transcripts or not an array - return original record
  .
end
