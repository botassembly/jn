#!/bin/bash
# Todo Tool Demo - JN-based Task Management
# Output format: Data to stdout (NDJSON), Events to stderr (JSONL)
set -e
cd "$(dirname "$0")"

# Use jn tool todo (alias is 'todo' after source activate.sh)
todo() { jn tool todo "$@"; }

# Create deterministic test data with fixed XIDs
cat > .todo.jsonl << 'EOF'
{"id":"ct5k9m8ag0001test0001","text":"Buy groceries","status":"pending","priority":"med","tags":[],"notes":[],"blockers":[],"parent":null,"due":null}
{"id":"ct5k9m8ag0002test0002","text":"Fix critical bug","status":"pending","priority":"high","tags":["@work"],"notes":[],"blockers":[],"parent":null,"due":null}
{"id":"ct5k9m8ag0003test0003","text":"Submit report","status":"done","priority":"med","tags":["@work"],"notes":[],"blockers":[],"parent":null,"due":"2024-12-20"}
{"id":"ct5k9m8ag0004test0004","text":"Review PR","status":"pending","priority":"low","tags":["@work","@review"],"notes":["Check the auth changes"],"blockers":[],"parent":null,"due":null}
{"id":"ct5k9m8ag0005test0005","text":"Write tests","status":"pending","priority":"med","tags":["@work"],"notes":[],"blockers":[],"parent":null,"due":null}
EOF

rm -f actual.txt

echo "=== Todo Demo ===" >> actual.txt
echo "" >> actual.txt

echo "1. List all todos:" >> actual.txt
todo list 2>/dev/null >> actual.txt
echo "" >> actual.txt

echo "2. List pending only:" >> actual.txt
todo list pending 2>/dev/null >> actual.txt
echo "" >> actual.txt

echo "3. Filter by priority:" >> actual.txt
todo list high 2>/dev/null >> actual.txt
echo "" >> actual.txt

echo "4. Filter by tag:" >> actual.txt
todo list @review 2>/dev/null >> actual.txt
echo "" >> actual.txt

echo "5. Search by text:" >> actual.txt
todo search bug 2>/dev/null >> actual.txt
echo "" >> actual.txt

echo "6. Show statistics:" >> actual.txt
todo stats 2>/dev/null >> actual.txt
echo "" >> actual.txt

echo "7. Quick count:" >> actual.txt
todo count 2>/dev/null >> actual.txt
echo "" >> actual.txt

echo "=== Done ===" >> actual.txt

# Cleanup
rm -f .todo.jsonl .todo.jsonl.bak

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
