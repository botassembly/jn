#!/bin/bash
# Bootstrap JN development environment using release binaries
# This speeds up development by providing pre-built plugins and tools

set -e

RELEASE_DIR="${1:-/tmp/jn-release}"
REPO="botassembly/jn"

echo "=== JN Release Bootstrap ==="

# Get latest release tag
echo "Fetching latest release..."
LATEST=$(curl -s "https://api.github.com/repos/$REPO/releases/latest" | grep '"tag_name"' | cut -d'"' -f4)

if [ -z "$LATEST" ]; then
    echo "Error: Could not fetch latest release"
    exit 1
fi

echo "Latest release: $LATEST"

# Construct download URL
VERSION="${LATEST#v}"
TARBALL="jn-${VERSION}-x86_64-linux.tar.gz"
URL="https://github.com/$REPO/releases/download/$LATEST/$TARBALL"

# Download and extract
echo "Downloading $TARBALL..."
mkdir -p "$RELEASE_DIR"
curl -L "$URL" -o "/tmp/$TARBALL"

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
