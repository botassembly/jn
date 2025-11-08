#!/usr/bin/env bash
# Demo script showing custom JC parser usage

set -e

echo "=== Custom JC Parser Demo ==="
echo ""

# Test 1: Direct parser test
echo "1. Testing parser directly:"
python3 jcparsers/keyvalue.py
echo ""

# Test 2: Parse sample data
echo "2. Parsing test_data.txt:"
cat test_data.txt | python3 -c '
import sys
sys.path.insert(0, "jcparsers")
import keyvalue
import json
data = sys.stdin.read()
result = keyvalue.parse(data)
print(json.dumps(result, indent=2))
'
echo ""

# Test 3: With JC library (if installed)
echo "3. Testing with jc library (if installed):"
if python3 -c "import jc" 2>/dev/null; then
    # Determine JC plugin directory
    if [[ "$OSTYPE" == "darwin"* ]]; then
        JC_DIR="$HOME/Library/Application Support/jc/jcparsers"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        JC_DIR="$LOCALAPPDATA/jc/jc/jcparsers"
    else
        if [[ -n "$XDG_DATA_HOME" ]]; then
            JC_DIR="$XDG_DATA_HOME/jc/jcparsers"
        else
            JC_DIR="$HOME/.local/share/jc/jcparsers"
        fi
    fi

    # Use the local jcparsers directory for demo
    cat test_data.txt | python3 -c "
import jc
import sys
jc.set_plugin_dir('jcparsers')
data = sys.stdin.read()
result = jc.parse('keyvalue', data)
import json
print(json.dumps(result, indent=2))
"
else
    echo "  jc not installed (pip install jc to enable)"
fi
echo ""

echo "=== Demo Complete ==="
