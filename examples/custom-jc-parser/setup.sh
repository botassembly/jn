#!/usr/bin/env bash
# Setup script to install custom JC parser

set -e

echo "Installing custom JC parser..."

# Determine the JC plugin directory based on OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    JC_DIR="$HOME/Library/Application Support/jc/jcparsers"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows
    JC_DIR="$LOCALAPPDATA/jc/jc/jcparsers"
else
    # Linux/Unix
    if [[ -n "$XDG_DATA_HOME" ]]; then
        JC_DIR="$XDG_DATA_HOME/jc/jcparsers"
    else
        JC_DIR="$HOME/.local/share/jc/jcparsers"
    fi
fi

echo "JC plugin directory: $JC_DIR"

# Create directory if it doesn't exist
mkdir -p "$JC_DIR"

# Copy the parser
cp jcparsers/keyvalue.py "$JC_DIR/"

echo "✓ Custom parser installed to: $JC_DIR/keyvalue.py"
echo ""
echo "Test the parser:"
echo "  python3 jcparsers/keyvalue.py"
echo "  cat test_data.txt | python3 -c 'import sys; sys.path.insert(0, \"$JC_DIR\"); import keyvalue; import json; print(json.dumps(keyvalue.parse(sys.stdin.read()), indent=2))'"
echo ""
echo "Or use with jc (if jc is installed and recognizes plugins):"
echo "  cat test_data.txt | python3 -c 'import jc; import sys; jc.set_plugin_dir(\"$JC_DIR\"); print(jc.parse(\"keyvalue\", sys.stdin.read()))'"
