#!/bin/bash
# ZQ vs jq Benchmark Script
# Usage: ./benchmark.sh [num_records]

set -e

NUM_RECORDS=${1:-100000}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZQ_BIN="${SCRIPT_DIR}/zig-out/bin/zq"
TEST_FILE="/tmp/zq_benchmark_${NUM_RECORDS}.ndjson"

# Check prerequisites
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required for benchmarking"
    exit 1
fi

if [ ! -f "$ZQ_BIN" ]; then
    echo "Building ZQ..."
    cd "$SCRIPT_DIR"
    zig build -Doptimize=ReleaseFast
fi

# Generate test data using Python (much faster than bash loop)
if [ ! -f "$TEST_FILE" ]; then
    echo "Generating $NUM_RECORDS test records..."
    python3 << EOF
import json
import random
with open("$TEST_FILE", "w") as f:
    for i in range(1, $NUM_RECORDS + 1):
        record = {
            "id": i,
            "value": random.randint(0, 100000),
            "name": f"user{i}",
            "active": random.choice([True, False]),
            "nested": {"score": random.randint(0, 1000)}
        }
        f.write(json.dumps(record) + "\n")
EOF
    echo "Test data saved to $TEST_FILE"
fi

echo ""
echo "=== ZQ vs jq Benchmark ==="
echo "Records: $NUM_RECORDS"
echo ""

# Benchmark function
benchmark() {
    local name="$1"
    local expr="$2"

    echo "--- $name ---"
    echo "Expression: $expr"

    # jq timing (3 runs, take best)
    echo -n "jq:  "
    best_jq="999"
    for i in 1 2 3; do
        t=$( { time cat "$TEST_FILE" | jq -c "$expr" > /dev/null; } 2>&1 | grep real | sed 's/real\s*//' )
        # Extract seconds as decimal
        secs=$(echo "$t" | sed 's/m/:/; s/s//' | awk -F: '{print $1 * 60 + $2}')
        if (( $(echo "$secs < $best_jq" | bc -l) )); then
            best_jq=$secs
        fi
    done
    printf "%.3fs\n" "$best_jq"

    # zq timing (3 runs, take best)
    echo -n "zq:  "
    best_zq="999"
    for i in 1 2 3; do
        t=$( { time cat "$TEST_FILE" | "$ZQ_BIN" "$expr" > /dev/null; } 2>&1 | grep real | sed 's/real\s*//' )
        secs=$(echo "$t" | sed 's/m/:/; s/s//' | awk -F: '{print $1 * 60 + $2}')
        if (( $(echo "$secs < $best_zq" | bc -l) )); then
            best_zq=$secs
        fi
    done
    printf "%.3fs\n" "$best_zq"

    # Speedup calculation
    if (( $(echo "$best_zq > 0" | bc -l) )); then
        speedup=$(echo "scale=2; $best_jq / $best_zq" | bc)
        echo "Speedup: ${speedup}x"
    fi
    echo ""
}

# Run benchmarks
benchmark "Identity" "."
benchmark "Field Access" ".name"
benchmark "Nested Path" ".nested.score"
benchmark "Select GT" "select(.value > 50000)"
benchmark "Select Eq" "select(.active == true)"

# Summary
echo "=== Summary ==="
echo "ZQ binary: $ZQ_BIN"
echo "ZQ size: $(ls -lh "$ZQ_BIN" | awk '{print $5}')"
echo "Test file: $TEST_FILE ($(ls -lh "$TEST_FILE" | awk '{print $5}'))"
