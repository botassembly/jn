#!/bin/sh
# JN installer script
# Usage: curl -sSfL https://raw.githubusercontent.com/botassembly/jn/main/install.sh | sh
#
# Environment variables:
#   JN_INSTALL_DIR  - Installation directory (default: ~/.local/jn)
#   JN_VERSION      - Specific version to install (default: latest)
#   JN_NO_MODIFY_PATH - Set to 1 to skip PATH modification

set -e

REPO="botassembly/jn"
INSTALL_DIR="${JN_INSTALL_DIR:-$HOME/.local/jn}"

# Colors (disabled if not a terminal)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

info() {
    printf "${BLUE}info${NC}: %s\n" "$1"
}

success() {
    printf "${GREEN}success${NC}: %s\n" "$1"
}

warn() {
    printf "${YELLOW}warn${NC}: %s\n" "$1"
}

error() {
    printf "${RED}error${NC}: %s\n" "$1" >&2
    exit 1
}

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Linux*)  echo "linux" ;;
        Darwin*) echo "darwin" ;;
        MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
        *) error "Unsupported operating system: $(uname -s)" ;;
    esac
}

# Detect architecture
detect_arch() {
    case "$(uname -m)" in
        x86_64|amd64) echo "x86_64" ;;
        aarch64|arm64) echo "aarch64" ;;
        *) error "Unsupported architecture: $(uname -m)" ;;
    esac
}

# Get latest version from GitHub API
get_latest_version() {
    if command -v curl >/dev/null 2>&1; then
        curl -sSf "https://api.github.com/repos/${REPO}/releases/latest" | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/'
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- "https://api.github.com/repos/${REPO}/releases/latest" | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/'
    else
        error "Neither curl nor wget found. Please install one of them."
    fi
}

# Download file
download() {
    url="$1"
    output="$2"

    if command -v curl >/dev/null 2>&1; then
        curl -sSfL "$url" -o "$output"
    elif command -v wget >/dev/null 2>&1; then
        wget -q "$url" -O "$output"
    else
        error "Neither curl nor wget found. Please install one of them."
    fi
}

# Detect shell config file
detect_shell_config() {
    case "${SHELL:-}" in
        */zsh)  echo "$HOME/.zshrc" ;;
        */bash) echo "$HOME/.bashrc" ;;
        */fish) echo "$HOME/.config/fish/config.fish" ;;
        *)
            # Fall back to checking what exists
            if [ -f "$HOME/.zshrc" ]; then
                echo "$HOME/.zshrc"
            elif [ -f "$HOME/.bashrc" ]; then
                echo "$HOME/.bashrc"
            else
                echo "$HOME/.profile"
            fi
            ;;
    esac
}

# Add to PATH
add_to_path() {
    shell_config=$(detect_shell_config)
    bin_dir="$INSTALL_DIR/bin"

    # Check if already in PATH
    case ":$PATH:" in
        *":$bin_dir:"*)
            info "Already in PATH"
            return 0
            ;;
    esac

    # Check if already in config
    if [ -f "$shell_config" ] && grep -q "$bin_dir" "$shell_config" 2>/dev/null; then
        info "PATH already configured in $shell_config"
        return 0
    fi

    if [ "${JN_NO_MODIFY_PATH:-}" = "1" ]; then
        warn "Skipping PATH modification (JN_NO_MODIFY_PATH=1)"
        echo ""
        echo "Add this to your shell config:"
        echo "  export PATH=\"$bin_dir:\$PATH\""
        return 0
    fi

    info "Adding to PATH in $shell_config"

    case "$shell_config" in
        *.fish)
            echo "" >> "$shell_config"
            echo "# JN" >> "$shell_config"
            echo "set -gx PATH \"$bin_dir\" \$PATH" >> "$shell_config"
            ;;
        *)
            echo "" >> "$shell_config"
            echo "# JN" >> "$shell_config"
            echo "export PATH=\"$bin_dir:\$PATH\"" >> "$shell_config"
            ;;
    esac

    success "Added to $shell_config"
}

main() {
    echo ""
    printf "${GREEN}JN Installer${NC}\n"
    echo ""

    OS=$(detect_os)
    ARCH=$(detect_arch)

    info "Detected OS: $OS"
    info "Detected arch: $ARCH"

    # Get version
    if [ -n "${JN_VERSION:-}" ]; then
        VERSION="$JN_VERSION"
        info "Installing version: $VERSION (specified)"
    else
        info "Fetching latest version..."
        VERSION=$(get_latest_version)
        if [ -z "$VERSION" ]; then
            error "Failed to get latest version. Try setting JN_VERSION manually."
        fi
        info "Latest version: $VERSION"
    fi

    # Construct download URL
    ARCHIVE="jn-${VERSION}-${ARCH}-${OS}.tar.gz"
    URL="https://github.com/${REPO}/releases/download/v${VERSION}/${ARCHIVE}"

    info "Downloading from: $URL"

    # Create temp directory
    TMP_DIR=$(mktemp -d)
    trap 'rm -rf "$TMP_DIR"' EXIT

    # Download
    download "$URL" "$TMP_DIR/$ARCHIVE" || error "Download failed. Check if version $VERSION exists for $ARCH-$OS."

    # Extract
    info "Installing to: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    tar -xzf "$TMP_DIR/$ARCHIVE" -C "$INSTALL_DIR" --strip-components=1

    # Verify
    if [ ! -x "$INSTALL_DIR/bin/jn" ]; then
        error "Installation failed: jn binary not found"
    fi

    success "Installed jn $VERSION"

    # Add to PATH
    add_to_path

    echo ""
    echo "---"
    echo ""
    success "Installation complete!"
    echo ""
    echo "To get started:"
    echo "  1. Restart your shell or run: source $(detect_shell_config)"
    echo "  2. Verify: jn --version"
    echo "  3. Try: echo '{\"hello\":\"world\"}' | jn filter '.'"
    echo ""
    echo "Documentation: https://github.com/${REPO}"
    echo ""
}

main "$@"
