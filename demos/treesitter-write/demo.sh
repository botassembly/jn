#!/bin/bash
# Tree-sitter Write Mode Demo - All 5 Phases
set -e
cd "$(dirname "$0")"
JN="${JN:-uv run jn}"

# Sample code
cat > sample.py << 'EOF'
class Calculator:
    def add(self, a, b):
        return a + b

@deprecated
def old_func():
    return "legacy"

def helper():
    pass
EOF

echo "=== Original Code ==="
cat sample.py
echo ""

# Phase 1: Body replacement
echo "=== Phase 1: Replace method body ==="
echo '{"target": "method:Calculator.add", "replace": "body", "code": "return a + b + 1"}' | \
  $JN plugin call treesitter_ --mode write --file sample.py | \
  $JN filter '.modified' | python3 -c "import json,sys; print(json.load(sys.stdin))" > result.py
grep -A2 "def add" result.py

# Phase 2: Multi-edit batch
echo ""
echo "=== Phase 2: Batch edit multiple targets ==="
cat > result.py << 'EOF'
def foo():
    return 1
def bar():
    return 2
EOF
echo '{"edits": [{"target": "function:foo", "replace": "body", "code": "return 10"}, {"target": "function:bar", "replace": "body", "code": "return 20"}]}' | \
  $JN plugin call treesitter_ --mode write --file result.py | \
  $JN filter '{success, edits_applied, targets}'

# Phase 3: Insert/Delete
echo ""
echo "=== Phase 3: Delete by target ==="
echo '{"operation": "delete", "target": "function:helper"}' | \
  $JN plugin call treesitter_ --mode write --file sample.py | \
  $JN filter '.modified' | python3 -c "import json,sys; print(json.load(sys.stdin))" | grep -c "def helper" || echo "helper() deleted!"

# Phase 4: Advanced targets
echo ""
echo "=== Phase 4: Target by decorator ==="
echo '{"target": "decorator:deprecated", "replace": "body", "code": "raise NotImplementedError()"}' | \
  $JN plugin call treesitter_ --mode write --file sample.py | \
  $JN filter '.modified' | python3 -c "import json,sys; print(json.load(sys.stdin))" | grep -A1 "@deprecated"

# Phase 5: Write-back with backup
echo ""
echo "=== Phase 5: Actual write with backup ==="
cp sample.py test_write.py
echo '{"target": "function:helper", "replace": "body", "code": "return 42"}' | \
  $JN plugin call treesitter_ --mode write --file test_write.py --write --backup --no-git-safe | \
  $JN filter '{success, file, backup}'

echo ""
echo "Backup created:"
ls -la *.bak 2>/dev/null || echo "(backup in temp location)"

# Cleanup
rm -f sample.py result.py test_write.py *.bak
echo ""
echo "=== Demo Complete ==="
