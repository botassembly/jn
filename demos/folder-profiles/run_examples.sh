#!/bin/bash
# Folder Profiles Demo - Query JSONL folders with named profiles
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Get jn-cat path (from dist or dev build)
if [ -f "../../dist/bin/jn-cat" ]; then
    JN_CAT="../../dist/bin/jn-cat"
elif [ -f "../../tools/zig/jn-cat/bin/jn-cat" ]; then
    JN_CAT="../../tools/zig/jn-cat/bin/jn-cat"
else
    echo "Error: jn-cat not found. Run 'make build' first."
    exit 1
fi

run() {
    echo "\$ $*"
    "$@" 2>/dev/null | sed "s|$SCRIPT_DIR/||g"
    echo ""
}

echo "=== Folder Profiles Demo ==="
echo ""

echo "# Query all events"
run $JN_CAT '@events/all'

echo "# Query login events only"
run $JN_CAT '@events/logins'

echo "# Query order events"
run $JN_CAT '@events/orders'

echo "# Query January events"
run $JN_CAT '@events/january'

echo "# Query CPU metrics"
run $JN_CAT '@metrics/cpu'

echo "# Query high CPU (>50%)"
run $JN_CAT '@metrics/high_cpu'

echo "# Query errors"
run $JN_CAT '@events/errors'

echo "=== Profile Structure ==="
echo ""
run find .jn/profiles/file -name '*.json' | sort

echo "# Example profile: events/logins.json"
run cat .jn/profiles/file/events/logins.json
