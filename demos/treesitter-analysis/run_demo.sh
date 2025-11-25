#!/bin/bash
# Tree-sitter Analysis Demo
#
# Demonstrates the Tree-sitter plugin's capabilities for:
# - Code analysis (read mode): symbols, calls, imports, skeleton, decorators
# - Surgical refactoring (write mode): body replacement, full replacement
#
# Usage: ./run_demo.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Use uv run jn if jn is not in PATH
if ! command -v jn &> /dev/null; then
  JN="uv run jn"
else
  JN="jn"
fi

echo "=============================================="
echo "Tree-sitter Code Analysis Demo"
echo "=============================================="
echo ""
echo "Sample module: sample_module.py"
echo ""

# Clean up previous output
rm -f symbols.json calls.json imports.json skeleton.json decorators.json
rm -f modified_*.py working_copy.py

# ============================================
# PART 1: READ MODE - Code Analysis
# ============================================

echo "=============================================="
echo "PART 1: CODE ANALYSIS (Read Mode)"
echo "=============================================="
echo ""

# Note: We pipe raw file content directly to the treesitter plugin
# because `jn cat file.py` auto-invokes the treesitter plugin

# --- Symbols Mode ---
echo "1. SYMBOLS - Extract functions, classes, and methods"
echo "   Command: cat sample_module.py | jn plugin call treesitter_ --mode read --output-mode symbols --filename sample_module.py"
echo ""
cat sample_module.py | \
  $JN plugin call treesitter_ --mode read --output-mode symbols --filename sample_module.py | \
  $JN put symbols.json
echo "   Results saved to symbols.json"
echo ""

echo "   Classes found:"
$JN cat symbols.json | $JN filter 'select(.type == "class")' | $JN filter '{name, start_line, end_line, lines}'
echo ""

echo "   Functions (not methods):"
$JN cat symbols.json | $JN filter 'select(.type == "function")' | $JN filter '{name, start_line, end_line}'
echo ""

echo "   Methods in Calculator class:"
$JN cat symbols.json | $JN filter 'select(.type == "method" and .parent_class == "Calculator")' | $JN filter '{name, parent_class, start_line}'
echo ""

# --- Calls Mode ---
echo "2. CALLS - Extract function call graph"
echo "   Command: cat sample_module.py | jn plugin call treesitter_ --mode read --output-mode calls --filename sample_module.py"
echo ""
cat sample_module.py | \
  $JN plugin call treesitter_ --mode read --output-mode calls --filename sample_module.py | \
  $JN put calls.json
echo "   Results saved to calls.json"
echo ""

echo "   Calls made from main():"
$JN cat calls.json | $JN filter 'select(.caller == "main")' | $JN filter '{caller, callee, line}'
echo ""

echo "   All method calls (self.*):"
$JN cat calls.json | $JN filter 'select(.callee | startswith("self."))' | $JN head -n 5
echo ""

# --- Imports Mode ---
echo "3. IMPORTS - Extract import statements"
echo "   Command: cat sample_module.py | jn plugin call treesitter_ --mode read --output-mode imports --filename sample_module.py"
echo ""
cat sample_module.py | \
  $JN plugin call treesitter_ --mode read --output-mode imports --filename sample_module.py | \
  $JN put imports.json
echo "   Results saved to imports.json"
echo ""

echo "   All imports:"
$JN cat imports.json | $JN filter '{module, names: .names, line}'
echo ""

# --- Skeleton Mode ---
echo "4. SKELETON - Generate code skeleton (bodies stripped)"
echo "   Command: cat sample_module.py | jn plugin call treesitter_ --mode read --output-mode skeleton --filename sample_module.py"
echo ""
cat sample_module.py | \
  $JN plugin call treesitter_ --mode read --output-mode skeleton --filename sample_module.py | \
  $JN put skeleton.json
echo "   Results saved to skeleton.json"
echo ""

# Extract skeleton content and show a portion
echo "   Skeleton preview (first 40 lines):"
$JN cat skeleton.json | $JN filter '.content' | head -n 1 | python3 -c "import json,sys; print(json.load(sys.stdin))" | head -n 40
echo "   ..."
echo ""

echo "   Functions stripped: $($JN cat skeleton.json | $JN filter '.functions_stripped' | head -n 1)"
echo ""

# --- Decorators Mode ---
echo "5. DECORATORS - Extract decorators and their targets"
echo "   Command: cat sample_module.py | jn plugin call treesitter_ --mode read --output-mode decorators --filename sample_module.py"
echo ""
cat sample_module.py | \
  $JN plugin call treesitter_ --mode read --output-mode decorators --filename sample_module.py | \
  $JN put decorators.json
echo "   Results saved to decorators.json"
echo ""

echo "   Decorators found:"
$JN cat decorators.json | $JN filter '{decorator, target, target_type, line}'
echo ""

# ============================================
# PART 2: WRITE MODE - Surgical Refactoring
# ============================================

echo "=============================================="
echo "PART 2: SURGICAL REFACTORING (Write Mode)"
echo "=============================================="
echo ""

# Make a working copy
cp sample_module.py working_copy.py

# --- Body Replacement ---
echo "6. BODY REPLACEMENT - Replace function body while preserving signature"
echo ""
echo "   Original validate_email function:"
grep -A 10 "def validate_email" working_copy.py | head -n 11
echo ""

echo "   Command: Replace body with regex-based validation"
echo '   {"target": "function:validate_email", "replace": "body", "code": "..."}'
echo ""

# Perform the replacement - code without extra indentation since _reindent handles it
echo '{"target": "function:validate_email", "replace": "body", "code": "import re\npattern = r\"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$\"\nreturn bool(re.match(pattern, email or \"\"))"}' | \
  $JN plugin call treesitter_ --mode write --file working_copy.py | \
  $JN filter '.modified' | \
  python3 -c "import json,sys; print(json.load(sys.stdin))" > modified_validate.py

echo "   Modified function (from dry-run output):"
grep -A 5 "def validate_email" modified_validate.py
echo ""

# --- Method Body Replacement ---
echo "7. METHOD REPLACEMENT - Replace method body in a class"
echo ""

# Reset working copy
cp sample_module.py working_copy.py

echo "   Original Calculator.add method:"
grep -A 5 "def add" working_copy.py | head -n 6
echo ""

echo "   Command: Add logging to the add method"
echo '   {"target": "method:Calculator.add", "replace": "body", "code": "..."}'
echo ""

# Code without indentation - _reindent will add proper indentation
echo '{"target": "method:Calculator.add", "replace": "body", "code": "print(f\"Adding {a} + {b}\")\nresult = a + b\nself.history.append(f\"add({a}, {b}) = {result}\")\nreturn result"}' | \
  $JN plugin call treesitter_ --mode write --file working_copy.py | \
  $JN filter '.modified' | \
  python3 -c "import json,sys; print(json.load(sys.stdin))" > modified_add.py

echo "   Modified method (from dry-run output):"
grep -A 6 "def add" modified_add.py | head -n 7
echo ""

# --- Full Function Replacement ---
echo "8. FULL REPLACEMENT - Replace entire function definition"
echo ""

# Reset working copy
cp sample_module.py working_copy.py

echo "   Original process_users function signature and body:"
grep -A 10 "def process_users" working_copy.py | head -n 11
echo ""

echo "   Command: Replace with async version"
echo "   New function will be async with timestamp"
echo ""

# Full replacement - use Python to properly construct JSON
python3 << 'PYEOF' | $JN plugin call treesitter_ --mode write --file working_copy.py > modified_process_result.json
import json
code = '''async def process_users_async(users: List[User]) -> dict:
    """Process users asynchronously."""
    if not users:
        return {"count": 0, "avg_age": 0}
    await asyncio.sleep(0.1)
    total_age = sum(u.age for u in users)
    return {"count": len(users), "avg_age": total_age / len(users)}'''
print(json.dumps({"target": "function:process_users", "replace": "full", "code": code}))
PYEOF

# Extract modified code
$JN cat modified_process_result.json | $JN filter '.modified' | \
  python3 -c "import json,sys; print(json.load(sys.stdin))" > modified_process.py

echo "   Modified function (from dry-run output):"
grep -A 6 "async def process_users" modified_process.py 2>/dev/null | head -n 8 || echo "   (check modified_process.py)"
echo ""

# Clean up working files
rm -f working_copy.py modified_process_result.json

# ============================================
# PART 3: JOINING WITH LCOV (Preview)
# ============================================

echo "=============================================="
echo "PART 3: LCOV JOIN COMPATIBILITY"
echo "=============================================="
echo ""
echo "Tree-sitter symbols include 'function' field for LCOV join:"
echo ""
$JN cat symbols.json | \
  $JN filter 'select(.type == "function" or .type == "method")' | \
  $JN filter '{file: .filename, function, type, start_line, end_line}' | \
  $JN head -n 5
echo ""
echo "This matches LCOV output format (file, function, start_line, end_line)"
echo "enabling joins like: jn cat coverage.lcov | jn join symbols.json --on function"
echo ""

# ============================================
# Summary
# ============================================

echo "=============================================="
echo "DEMO COMPLETE"
echo "=============================================="
echo ""
echo "Output files:"
echo "  - symbols.json    : Functions, classes, methods with line numbers"
echo "  - calls.json      : Function call graph"
echo "  - imports.json    : Import statements"
echo "  - skeleton.json   : Code skeleton (bodies stripped)"
echo "  - decorators.json : Decorators and their targets"
echo "  - modified_*.py   : Examples of surgical code modifications"
echo ""
echo "Try these commands:"
echo ""
echo "  # Extract all symbols from a Python file"
echo "  cat mycode.py | jn plugin call treesitter_ --mode read --output-mode symbols --filename mycode.py"
echo ""
echo "  # Generate skeleton for LLM context"
echo "  cat mycode.py | jn plugin call treesitter_ --mode read --output-mode skeleton --filename mycode.py"
echo ""
echo "  # Replace function body"
echo '  echo '"'"'{"target": "function:foo", "replace": "body", "code": "return 42"}'"'"' | \\'
echo "    jn plugin call treesitter_ --mode write --file mycode.py"
echo ""
echo "  # Find all API routes (decorators)"
echo "  cat app.py | jn plugin call treesitter_ --mode read --output-mode decorators --filename app.py | \\"
echo '    jn filter '"'"'select(.decorator | contains("route"))'"'"
echo ""
