#!/bin/bash
# Run All Demos - Execute all JN demo scripts
#
# This script runs each demo and reports pass/fail status.
# Use --continue-on-error to run all demos even if some fail.

# Don't use set -e as ((PASSED++)) can return non-zero

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SCRIPT_DIR"

# Set up environment - source activate.sh if available
if [ -f "$PROJECT_ROOT/dist/activate.sh" ]; then
    source "$PROJECT_ROOT/dist/activate.sh"
fi

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

run_demo() {
    local dir="$1"
    local name="$2"

    if [ ! -f "$dir/run.sh" ]; then
        echo -e "${YELLOW}SKIP${NC} $name (run.sh not found)"
        SKIPPED=$((SKIPPED + 1))
        return 0
    fi

    echo -n "Running $name... "

    # Run in subshell to isolate directory changes
    if (cd "$dir" && bash run.sh > /dev/null 2>&1); then
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

# Run all demos
echo "--- Demo Suite ---"
run_demo "csv-filtering" "CSV Filtering"
run_demo "join" "Join Operations"
run_demo "shell-commands" "Shell Commands"
run_demo "glob" "Glob Patterns"
run_demo "http-api" "HTTP API"
run_demo "xlsx-files" "Excel Files"
run_demo "table-rendering" "Table Rendering"
run_demo "markdown-skills" "Markdown Skills"
run_demo "adapter-merge" "Adapter Merge"
run_demo "code-lcov" "Code Coverage"
run_demo "folder-profiles" "Folder Profiles"
run_demo "jn-grep" "JN Grep"
run_demo "json-editing" "JSON Editing"
run_demo "todo" "Todo Tool"
run_demo "zq-functions" "ZQ Functions"
run_demo "genomoncology" "GenomOncology Profiles"

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
    echo "All demos passed!"
fi
