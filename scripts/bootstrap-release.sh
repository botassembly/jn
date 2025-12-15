#!/bin/bash
# Bootstrap JN development environment using release binaries
# This speeds up development by providing pre-built plugins and tools

set -e

RELEASE_DIR="${1:-/tmp/jn-release}"
REPO="botassembly/jn"

echo "=== JN Release Bootstrap ==="

# Try consistent filename first (new releases), fall back to versioned (old releases)
TARBALL="jn-linux-x86_64.tar.gz"
URL="https://github.com/$REPO/releases/latest/download/$TARBALL"

echo "Downloading latest release..."
mkdir -p "$RELEASE_DIR"

if ! curl -fL "$URL" -o "/tmp/$TARBALL" 2>/dev/null; then
    echo "Consistent filename not found, fetching versioned release..."
    LATEST=$(curl -s "https://api.github.com/repos/$REPO/releases/latest" | grep '"tag_name"' | cut -d'"' -f4)
    VERSION="${LATEST#v}"
    TARBALL="jn-${VERSION}-x86_64-linux.tar.gz"
    URL="https://github.com/$REPO/releases/download/$LATEST/$TARBALL"
    curl -fL "$URL" -o "/tmp/$TARBALL"
fi

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
