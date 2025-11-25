# Filter sales above threshold
# Parameters: threshold
select((.amount | tonumber) > ($threshold | tonumber))
