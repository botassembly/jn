#!/bin/bash
# Run All Demos - Execute all JN demo scripts
#
# This script runs each demo and reports pass/fail status.
# Use --continue-on-error to run all demos even if some fail.

# Don't use set -e as ((PASSED++)) can return non-zero

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SCRIPT_DIR"

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

# Run demos in order of complexity
echo "--- Core Demos ---"
run_demo "csv-filtering" "run_examples.sh" "CSV Filtering"
run_demo "glob" "run_examples.sh" "Glob Patterns"
run_demo "join" "run_examples.sh" "Join Operations"
run_demo "table-rendering" "run_examples.sh" "Table Rendering"

echo ""
echo "--- Format Demos ---"
run_demo "xlsx-files" "run_examples.sh" "Excel Files"

echo ""
echo "--- Protocol Demos ---"
run_demo "http-api" "run_examples.sh" "HTTP API"
run_demo "shell-commands" "run_examples.sh" "Shell Commands"

echo ""
echo "--- Advanced Demos ---"
run_demo "adapter-merge" "run_examples.sh" "Adapter Merge"

# Code Coverage demo requires coverage.lcov file - generate if missing
if [ ! -f "$PROJECT_ROOT/coverage.lcov" ]; then
    echo -n "Generating coverage.lcov... "
    if (cd "$PROJECT_ROOT" && make coverage > /dev/null 2>&1); then
        echo -e "${GREEN}done${NC}"
    else
        echo -e "${RED}failed${NC}"
    fi
fi

if [ -f "$PROJECT_ROOT/coverage.lcov" ]; then
    run_demo "code-lcov" "run_demo.sh" "Code Coverage (LCOV)"
else
    echo -e "${YELLOW}SKIP${NC} Code Coverage (LCOV) (make coverage failed)"
    SKIPPED=$((SKIPPED + 1))
fi

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
