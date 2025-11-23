#!/bin/bash
# Shell Commands Demo - Run Examples

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

echo "1. List files in current directory..."
jn sh "ls -la" | jn head -n 10 | jn put file_list.json
echo "   ✓ Created file_list.json (first 10 files)"
echo ""

echo "2. Find top processes by CPU..."
if jn sh "ps aux" > /dev/null 2>&1; then
    jn sh "ps aux" | \
      jq -s 'sort_by(.pcpu | tonumber) | reverse | .[:10] | .[]' | \
      jn filter '{user: .user, pid: .pid, cpu: .pcpu, mem: .pmem, command: (.command[:50])}' | \
      jn put top_processes.json
    echo "   ✓ Created top_processes.json (top 10)"
else
    echo "   ⚠ Skipped (ps command not available or jc not installed)"
fi
echo ""

echo "3. Check disk usage..."
if jn sh "df" > /dev/null 2>&1; then
    jn sh "df" | \
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

echo "4. Extract key environment variables..."
if jn sh "env" > /dev/null 2>&1; then
    jn sh "env" | \
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
    echo "Current user:"
    jq -r '.[] | select(.variable == "USER") | .value' env_vars.json 2>/dev/null || echo "N/A"
fi

echo ""
echo "All examples completed! Check the output files."
