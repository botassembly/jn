#!/bin/bash
# Bootstrap JN development environment using release binaries
# This speeds up development by providing pre-built plugins and tools

set -e

RELEASE_DIR="${1:-/tmp/jn-release}"
REPO="botassembly/jn"
TARBALL="jn-linux-x86_64.tar.gz"

echo "=== JN Release Bootstrap ==="

# Download URL (uses consistent filename that always points to latest)
URL="https://github.com/$REPO/releases/latest/download/$TARBALL"

# Download and extract
echo "Downloading latest release..."
mkdir -p "$RELEASE_DIR"
curl -fL "$URL" -o "/tmp/$TARBALL"

echo "Extracting to $RELEASE_DIR..."
tar -xzf "/tmp/$TARBALL" -C "$RELEASE_DIR" --strip-components=1
rm -f "/tmp/$TARBALL"

# Verify
if [ -x "$RELEASE_DIR/bin/jn" ]; then
    echo ""
    echo "=== Bootstrap Complete ==="
    echo ""
    echo "Release installed to: $RELEASE_DIR"
    echo "Version: $("$RELEASE_DIR/bin/jn" --version)"
    echo ""
    echo "To use, run:"
    echo "  export JN_HOME=\"$RELEASE_DIR\""
    echo "  export PATH=\"\$JN_HOME/bin:\$PATH\""
    echo ""
    echo "Or add to your shell config:"
    echo "  echo 'export JN_HOME=\"$RELEASE_DIR\"' >> ~/.bashrc"
    echo "  echo 'export PATH=\"\$JN_HOME/bin:\$PATH\"' >> ~/.bashrc"
else
    echo "Error: Bootstrap failed - jn binary not found"
    exit 1
fi
