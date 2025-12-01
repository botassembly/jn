# Filter sales above threshold
# Parameters: threshold (numeric)
select((.amount | tonumber) > $threshold)
