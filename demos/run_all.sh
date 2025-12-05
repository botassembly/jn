#!/bin/bash
# Run All Demos - Execute all JN demo scripts
#
# This script runs each demo and reports pass/fail status.
# Use --continue-on-error to run all demos even if some fail.

# Don't use set -e as ((PASSED++)) can return non-zero

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SCRIPT_DIR"

# Set up environment for Zig tools
export JN_HOME="${JN_HOME:-$PROJECT_ROOT}"
export PATH="$PROJECT_ROOT/tools/zig/jn/bin:$PATH"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track results
PASSED=0
FAILED=0
SKIPPED=0
FAILED_DEMOS=""

# Parse arguments
CONTINUE_ON_ERROR=false
if [ "$1" = "--continue-on-error" ]; then
    CONTINUE_ON_ERROR=true
fi

echo "========================================"
echo "       JN Demo Suite Runner"
echo "========================================"
echo ""
echo "JN_HOME: $JN_HOME"
echo "PATH includes: $PROJECT_ROOT/tools/zig/jn/bin"
echo ""

run_demo() {
    local dir="$1"
    local script="$2"
    local name="$3"

    if [ ! -f "$dir/$script" ]; then
        echo -e "${YELLOW}SKIP${NC} $name (script not found)"
        SKIPPED=$((SKIPPED + 1))
        return 0
    fi

    echo -n "Running $name... "

    # Run in subshell to isolate directory changes
    if (cd "$dir" && bash "$script" > /dev/null 2>&1); then
        echo -e "${GREEN}PASS${NC}"
        PASSED=$((PASSED + 1))
    else
        echo -e "${RED}FAIL${NC}"
        FAILED=$((FAILED + 1))
        FAILED_DEMOS="$FAILED_DEMOS\n  - $name"
        if [ "$CONTINUE_ON_ERROR" = false ]; then
            echo ""
            echo "Demo failed. Use --continue-on-error to run remaining demos."
            exit 1
        fi
    fi
}

skip_demo() {
    local name="$1"
    local reason="$2"
    echo -e "${YELLOW}SKIP${NC} $name ($reason)"
    SKIPPED=$((SKIPPED + 1))
}

# Run demos - only working ones by default
echo "--- Working Demos ---"
run_demo "csv-filtering" "run_examples.sh" "CSV Filtering"
run_demo "join" "run_examples.sh" "Join Operations"

echo ""
echo "--- Partial Support ---"
run_demo "shell-commands" "run_examples.sh" "Shell Commands"

echo ""
echo "--- Pending Features ---"
skip_demo "Glob Patterns" "glob patterns not yet in Zig"
skip_demo "HTTP API" "remote URLs pending OpenDAL"
skip_demo "Excel Files" "Python plugin discovery pending"
skip_demo "Table Rendering" "jn table not yet in Zig"
skip_demo "Adapter Merge" "DuckDB Python plugin pending"
skip_demo "Code Coverage" "Python @code profiles pending"

echo ""
echo "========================================"
echo "             Summary"
echo "========================================"
echo -e "  ${GREEN}Passed:${NC}  $PASSED"
echo -e "  ${RED}Failed:${NC}  $FAILED"
echo -e "  ${YELLOW}Skipped:${NC} $SKIPPED"
echo ""

if [ $FAILED -gt 0 ]; then
    echo -e "Failed demos:$FAILED_DEMOS"
    echo ""
    exit 1
else
    echo "Working demos passed! See README.md for pending features."
fi
