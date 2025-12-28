#!/bin/bash
# Zig Code Coverage Script using kcov
#
# This script collects code coverage from all Zig tests and produces:
#   - HTML report at zig-out/coverage/html/
#   - LCOV file at zig-out/coverage/lcov.info
#   - Merged kcov output at zig-out/coverage/merged/
#
# Requirements:
#   - kcov (https://github.com/SimonKagstrom/kcov)
#   - Zig compiler
#
# Usage:
#   ./scripts/coverage.sh           # Run coverage collection
#   ./scripts/coverage.sh --check   # Just check if kcov is available
#   ./scripts/coverage.sh --install # Build and install kcov from source

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COV_OUTPUT="$PROJECT_ROOT/zig-out/coverage"
KCOV_OUTPUT="$COV_OUTPUT/kcov"
MERGED_OUTPUT="$COV_OUTPUT/merged"
HTML_OUTPUT="$COV_OUTPUT/html"
LCOV_OUTPUT="$COV_OUTPUT/lcov.info"
COBERTURA_OUTPUT="$COV_OUTPUT/cobertura.xml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Source directories to include in coverage
INCLUDE_PATTERNS="--include-pattern=libs/zig/ --include-pattern=plugins/zig/ --include-pattern=tools/zig/ --include-pattern=zq/src/"
EXCLUDE_PATTERNS="--exclude-pattern=.zig-cache --exclude-pattern=zig-out"

# Module definitions (same as Makefile)
PLUGIN_MODULES="--dep jn-core --dep jn-cli --dep jn-plugin \
    -Mroot=main.zig \
    -Mjn-core=../../../libs/zig/jn-core/src/root.zig \
    -Mjn-cli=../../../libs/zig/jn-cli/src/root.zig \
    -Mjn-plugin=../../../libs/zig/jn-plugin/src/root.zig"

TOOL_MODULES="--dep jn-core --dep jn-cli --dep jn-address --dep jn-profile \
    -Mroot=main.zig \
    -Mjn-core=../../../libs/zig/jn-core/src/root.zig \
    -Mjn-cli=../../../libs/zig/jn-cli/src/root.zig \
    -Mjn-address=../../../libs/zig/jn-address/src/root.zig \
    -Mjn-profile=../../../libs/zig/jn-profile/src/root.zig"

JN_MODULES="--dep jn-core \
    -Mroot=main.zig \
    -Mjn-core=../../../libs/zig/jn-core/src/root.zig"

# Libraries to test
LIBS=(jn-core jn-cli jn-plugin jn-address jn-profile jn-discovery)

# Plugins to test
PLUGINS=(csv json jsonl gz yaml toml)

# Tools to test
TOOLS=(jn-cat jn-put jn-filter jn-head jn-tail jn-analyze jn-inspect jn-join jn-merge jn-sh jn-edit)

# Find Zig compiler
find_zig() {
    local ZIG_VERSION=0.15.2
    local ZIG_LOCAL="$HOME/.local/zig-x86_64-linux-$ZIG_VERSION"
    if [ -x "$ZIG_LOCAL/zig" ]; then
        ZIG="$ZIG_LOCAL/zig"
    elif command -v zig &>/dev/null; then
        ZIG="zig"
    else
        echo -e "${RED}Error: Zig not found. Run 'make install-zig' first.${NC}"
        exit 1
    fi
}

# Check if kcov is available
check_kcov() {
    if command -v kcov &>/dev/null; then
        echo -e "${GREEN}kcov found:${NC} $(which kcov)"
        kcov --version 2>/dev/null || true
        return 0
    else
        echo -e "${RED}kcov not found${NC}"
        echo ""
        echo "To install kcov, run one of:"
        echo "  ./scripts/coverage.sh --install    # Build from source"
        echo "  sudo apt-get install kcov          # Ubuntu (if available)"
        echo "  brew install kcov                  # macOS"
        echo ""
        echo "Or build manually:"
        echo "  git clone https://github.com/SimonKagstrom/kcov.git"
        echo "  cd kcov && mkdir build && cd build"
        echo "  cmake .. && make && sudo make install"
        return 1
    fi
}

# Install kcov from pre-built binary or source
install_kcov() {
    echo -e "${YELLOW}Installing kcov...${NC}"

    # Try downloading pre-built binary first (faster, no build deps needed)
    local KCOV_VERSION="v42"
    local KCOV_URL="https://github.com/SimonKagstrom/kcov/releases/download/${KCOV_VERSION}/kcov-amd64.tar.gz"
    local KCOV_TMP="/tmp/kcov-install-$$"

    mkdir -p "$KCOV_TMP"

    echo "Downloading kcov ${KCOV_VERSION}..."
    if curl -L -o "$KCOV_TMP/kcov.tar.gz" "$KCOV_URL" 2>/dev/null; then
        tar -xzf "$KCOV_TMP/kcov.tar.gz" -C "$KCOV_TMP"

        if [ -f "$KCOV_TMP/usr/local/bin/kcov" ]; then
            sudo cp "$KCOV_TMP/usr/local/bin/kcov" /usr/local/bin/

            # Create symlinks for binutils library compatibility
            # kcov v42 was built against binutils 2.38, adapt to system version
            local SYSTEM_BFD=$(find /usr/lib -name "libbfd-*.so" 2>/dev/null | head -1)
            local SYSTEM_OPCODES=$(find /usr/lib -name "libopcodes-*.so" 2>/dev/null | head -1)

            if [ -n "$SYSTEM_BFD" ] && [ -n "$SYSTEM_OPCODES" ]; then
                local BFD_DIR=$(dirname "$SYSTEM_BFD")
                sudo ln -sf "$SYSTEM_BFD" "$BFD_DIR/libbfd-2.38-system.so" 2>/dev/null || true
                sudo ln -sf "$SYSTEM_OPCODES" "$BFD_DIR/libopcodes-2.38-system.so" 2>/dev/null || true
            fi

            rm -rf "$KCOV_TMP"

            if kcov --version >/dev/null 2>&1; then
                echo -e "${GREEN}kcov installed successfully from pre-built binary${NC}"
                kcov --version
                return 0
            fi
        fi
    fi

    rm -rf "$KCOV_TMP"

    # Fall back to building from source
    echo "Pre-built binary failed, building from source..."

    # Check dependencies
    if ! dpkg -l | grep -q libelf-dev; then
        echo "Installing build dependencies..."
        sudo apt-get update
        sudo apt-get install -y cmake libelf-dev libdw-dev libcurl4-openssl-dev
    fi

    # Build kcov
    BUILD_DIR="/tmp/kcov-build-$$"
    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR"

    git clone --depth 1 https://github.com/SimonKagstrom/kcov.git
    cd kcov
    mkdir build && cd build
    cmake ..
    make -j$(nproc)
    sudo make install

    # Cleanup
    rm -rf "$BUILD_DIR"

    echo -e "${GREEN}kcov installed successfully${NC}"
    kcov --version
}

# Build and run a test under kcov
run_test_with_coverage() {
    local name="$1"
    local source_dir="$2"
    local source_file="$3"
    local modules="$4"

    echo -e "  ${YELLOW}Testing:${NC} $name"

    local test_bin="$PROJECT_ROOT/zig-out/test-bin/$name"
    local kcov_dir="$KCOV_OUTPUT/$name"

    mkdir -p "$(dirname "$test_bin")"

    # Build test binary with debug info (no optimization for better coverage)
    cd "$source_dir"
    if [ -n "$modules" ]; then
        $ZIG test $modules "$source_file" -fllvm -O Debug -femit-bin="$test_bin" 2>&1 || {
            echo -e "    ${RED}Build failed${NC}"
            return 1
        }
    else
        $ZIG test "$source_file" -fllvm -O Debug -femit-bin="$test_bin" 2>&1 || {
            echo -e "    ${RED}Build failed${NC}"
            return 1
        }
    fi

    # Run under kcov
    kcov --clean $INCLUDE_PATTERNS $EXCLUDE_PATTERNS "$kcov_dir" "$test_bin" 2>&1 || {
        echo -e "    ${RED}kcov failed${NC}"
        return 1
    }

    echo -e "    ${GREEN}OK${NC}"
}

# Run all tests with coverage
run_all_coverage() {
    # Find Zig compiler first
    find_zig

    echo -e "${YELLOW}Collecting Zig code coverage...${NC}"
    echo ""

    # Clean previous coverage
    rm -rf "$COV_OUTPUT"
    mkdir -p "$KCOV_OUTPUT"
    mkdir -p "$PROJECT_ROOT/zig-out/test-bin"

    local failed=0

    # Test libraries
    echo "Testing libraries..."
    for lib in "${LIBS[@]}"; do
        run_test_with_coverage "$lib" "$PROJECT_ROOT/libs/zig/$lib" "src/root.zig" "" || ((failed++))
    done

    # Test plugins
    echo ""
    echo "Testing plugins..."
    for plugin in "${PLUGINS[@]}"; do
        run_test_with_coverage "plugin-$plugin" "$PROJECT_ROOT/plugins/zig/$plugin" "main.zig" "$PLUGIN_MODULES" || ((failed++))
    done

    # Test tools
    echo ""
    echo "Testing tools..."
    for tool in "${TOOLS[@]}"; do
        run_test_with_coverage "$tool" "$PROJECT_ROOT/tools/zig/$tool" "main.zig" "$TOOL_MODULES" || ((failed++))
    done

    # Test jn orchestrator (uses different modules)
    run_test_with_coverage "jn" "$PROJECT_ROOT/tools/zig/jn" "main.zig" "$JN_MODULES" || ((failed++))

    # Test ZQ
    echo ""
    echo "Testing ZQ..."
    run_test_with_coverage "zq-main" "$PROJECT_ROOT/zq" "src/main.zig" "" || ((failed++))
    run_test_with_coverage "zq-integration" "$PROJECT_ROOT/zq" "tests/integration.zig" "" || ((failed++))

    echo ""

    if [ $failed -gt 0 ]; then
        echo -e "${RED}$failed test(s) failed${NC}"
    fi

    # Merge all coverage data
    echo -e "${YELLOW}Merging coverage data...${NC}"
    kcov --merge "$MERGED_OUTPUT" "$KCOV_OUTPUT"/*

    # Copy merged HTML report
    mkdir -p "$HTML_OUTPUT"
    cp -r "$MERGED_OUTPUT"/* "$HTML_OUTPUT/"

    # Extract LCOV from kcov output
    # kcov generates cobertura.xml which we can convert, or use the lcov.info if available
    if [ -f "$MERGED_OUTPUT/kcov-merged/cobertura.xml" ]; then
        cp "$MERGED_OUTPUT/kcov-merged/cobertura.xml" "$COBERTURA_OUTPUT"
    fi

    # Generate LCOV summary
    echo ""
    echo -e "${GREEN}=== Coverage Summary ===${NC}"
    echo ""

    # Try to extract coverage percentage from kcov output
    if [ -f "$MERGED_OUTPUT/kcov-merged/coverage.json" ]; then
        local percent=$(jq -r '.percent_covered // "N/A"' "$MERGED_OUTPUT/kcov-merged/coverage.json" 2>/dev/null || echo "N/A")
        local covered=$(jq -r '.covered_lines // "N/A"' "$MERGED_OUTPUT/kcov-merged/coverage.json" 2>/dev/null || echo "N/A")
        local total=$(jq -r '.total_lines // "N/A"' "$MERGED_OUTPUT/kcov-merged/coverage.json" 2>/dev/null || echo "N/A")
        echo "Coverage: ${percent}% ($covered/$total lines)"
    fi

    echo ""
    echo "Reports generated:"
    echo "  HTML:      $HTML_OUTPUT/index.html"
    if [ -f "$COBERTURA_OUTPUT" ]; then
        echo "  Cobertura: $COBERTURA_OUTPUT"
    fi
    echo ""
    echo "Open the HTML report:"
    echo "  open $HTML_OUTPUT/index.html"

    return $failed
}

# Main
case "${1:-}" in
    --check)
        check_kcov
        exit $?
        ;;
    --install)
        install_kcov
        exit $?
        ;;
    --help|-h)
        echo "Usage: $0 [--check|--install|--help]"
        echo ""
        echo "Options:"
        echo "  --check    Check if kcov is available"
        echo "  --install  Build and install kcov from source"
        echo "  --help     Show this help message"
        echo ""
        echo "Without options, runs coverage collection for all Zig code."
        exit 0
        ;;
    "")
        if ! check_kcov; then
            exit 1
        fi
        run_all_coverage
        exit $?
        ;;
    *)
        echo "Unknown option: $1"
        echo "Use --help for usage information."
        exit 1
        ;;
esac
