#!/bin/bash
# Shell Commands Demo - Converting Shell Output to NDJSON
#
# Demonstrates:
# - Using jn sh to convert shell commands to NDJSON
# - Processing system info (ls, ps, df, env)
# - Filtering shell command output
# - Requires jc (JSON Convert) installed: pip install jc

set -e

echo "=== JN Shell Commands Demo ==="
echo ""

# Check if jc is installed
if ! command -v jc &> /dev/null; then
    echo "WARNING: jc (JSON Convert) is not installed"
    echo "Some examples may not work. Install with: pip install jc"
    echo ""
fi

# Clean up previous output
rm -f file_list.json top_processes.json disk_usage.json env_vars.json

# Example 1: Convert ls output to NDJSON
# jn sh COMMAND (no quotes!) - passes command to shell
# jc parses ls output to NDJSON format
# jn head limits output, jn put saves to file
echo "1. List files in current directory..."
jn sh ls -la | jn head -n 10 | jn put file_list.json
echo "   ✓ Created file_list.json (first 10 files)"
echo ""

# Example 2: Process list with filtering
# ps aux output → NDJSON with fields like cpu_percent, mem_percent
# jq -sc: slurp + compact (sort entire list, output as NDJSON)
# // 0 handles null CPU values
echo "2. Find top processes by CPU..."
if jn sh ps aux > /dev/null 2>&1; then
    jn sh ps aux | \
      jq -sc 'sort_by(.cpu_percent // 0) | reverse | .[:10] | .[]' | \
      jn filter '{user: .user, pid: .pid, cpu: .cpu_percent, mem: .mem_percent, command: (.command[:50])}' | \
      jn put top_processes.json
    echo "   ✓ Created top_processes.json (top 10)"
else
    echo "   ⚠ Skipped (ps command not available or jc not installed)"
fi
echo ""

# Example 3: Disk usage filtering
# df output → NDJSON, select only /dev/* filesystems
# select() is jq's filter function (like grep)
echo "3. Check disk usage..."
if jn sh df > /dev/null 2>&1; then
    jn sh df | \
      jn filter 'select(.filesystem | startswith("/dev/")) | {
        filesystem: .filesystem,
        use_percent: .use_percent,
        mounted: .mounted_on
      }' | \
      jn put disk_usage.json
    echo "   ✓ Created disk_usage.json"
else
    echo "   ⚠ Skipped (df command not available or jc not installed)"
fi
echo ""

# Example 4: Extract specific environment variables
# env command → NDJSON with {name, value} objects
# test() is jq regex match function
echo "4. Extract key environment variables..."
if jn sh env > /dev/null 2>&1; then
    jn sh env | \
      jn filter 'select(.name | test("^(HOME|USER|SHELL|PATH|PWD)$")) | {
        variable: .name,
        value: .value
      }' | \
      jn put env_vars.json
    echo "   ✓ Created env_vars.json"
else
    echo "   ⚠ Skipped (env command not available or jc not installed)"
fi
echo ""

# Show results
echo "=== Results ==="
echo ""

if [ -f file_list.json ]; then
    echo "Files listed: $(jq -s 'length' file_list.json)"
    echo "First file: $(jq -s '.[0].filename' file_list.json 2>/dev/null || echo 'N/A')"
fi

if [ -f top_processes.json ]; then
    echo ""
    echo "Top process by CPU:"
    jq -s '.[0] | "\(.user) - \(.command) (CPU: \(.cpu)%)"' top_processes.json 2>/dev/null || echo "N/A"
fi

if [ -f disk_usage.json ]; then
    echo ""
    echo "Disk usage for root:"
    jq -s '.[] | select(.mounted == "/") | "Filesystem \(.filesystem): \(.use_percent)% used"' disk_usage.json 2>/dev/null || echo "N/A"
fi

if [ -f env_vars.json ]; then
    echo ""
    echo "Home directory:"
    jq -r '.[] | select(.variable == "HOME") | .value' env_vars.json 2>/dev/null || echo "N/A"
fi

echo ""
echo "All examples completed! Check the output files."
