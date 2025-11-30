#!/bin/bash
# Glob Demo - Reading Multiple Files with Pattern Matching
#
# Demonstrates:
# - Glob patterns for reading multiple files (*.jsonl, **/*.json)
# - Compressed file handling (*.jsonl.gz, *.csv.gz)
# - Path metadata injection (_path, _dir, _filename, _ext)
# - Filtering by path components
# - Multi-format globbing

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== JN Glob Demo ==="
echo ""

# Create test data directory structure
echo "Setting up test data..."
rm -rf test_data output
mkdir -p test_data/logs/2024-01 test_data/logs/2024-02
mkdir -p test_data/events/completed test_data/events/failed
mkdir -p output

# Create JSONL log files
cat > test_data/logs/2024-01/access.jsonl << 'EOF'
{"timestamp": "2024-01-15T10:30:00Z", "level": "INFO", "message": "User login", "user_id": 123}
{"timestamp": "2024-01-15T10:31:00Z", "level": "ERROR", "message": "Connection failed", "user_id": 456}
{"timestamp": "2024-01-15T10:32:00Z", "level": "INFO", "message": "Data sync", "user_id": 123}
EOF

cat > test_data/logs/2024-02/access.jsonl << 'EOF'
{"timestamp": "2024-02-01T09:00:00Z", "level": "WARN", "message": "Rate limit", "user_id": 789}
{"timestamp": "2024-02-01T09:05:00Z", "level": "ERROR", "message": "Auth failed", "user_id": 101}
EOF

# Create compressed JSONL file
cat > test_data/logs/2024-02/metrics.jsonl << 'EOF'
{"metric": "cpu", "value": 45.2, "host": "server1"}
{"metric": "memory", "value": 78.5, "host": "server1"}
{"metric": "cpu", "value": 32.1, "host": "server2"}
EOF
gzip test_data/logs/2024-02/metrics.jsonl

# Create event JSON files
echo '{"event": "process_start", "id": "job-001", "status": "running"}' > test_data/events/completed/job1.json
echo '{"event": "process_end", "id": "job-001", "status": "success"}' > test_data/events/completed/job2.json
echo '{"event": "process_error", "id": "job-002", "status": "failed", "error": "timeout"}' > test_data/events/failed/job3.json

# Create CSV file
cat > test_data/events/summary.csv << 'EOF'
job_id,status,duration_ms
job-001,success,1234
job-002,failed,5678
job-003,success,890
EOF

echo "   Created test data in test_data/"
echo ""

# Example 1: Basic glob pattern
echo "1. Read all JSONL files recursively..."
jn cat 'test_data/**/*.jsonl' | jn head -n 5 | jn put output/all_logs.json
echo "   ✓ Created output/all_logs.json (first 5 records)"
echo ""

# Example 2: Compressed file handling
echo "2. Read compressed JSONL files (*.jsonl.gz)..."
jn cat 'test_data/**/*.jsonl.gz' | jn put output/metrics.json
echo "   ✓ Created output/metrics.json (decompressed automatically)"
echo ""

# Example 3: Filter by path metadata
echo "3. Filter by directory path (January logs only)..."
jn cat 'test_data/**/*.jsonl' | \
  jn filter 'select(._dir | contains("2024-01"))' | \
  jn put output/january_logs.json
echo "   ✓ Created output/january_logs.json"
echo ""

# Example 4: Group errors by file
echo "4. Find all ERROR level entries with source file..."
jn cat 'test_data/**/*.jsonl' | \
  jn filter 'select(.level == "ERROR") | {file: ._filename, message: .message, user: .user_id}' | \
  jn put output/errors.json
echo "   ✓ Created output/errors.json"
echo ""

# Example 5: Multi-format glob (JSON files)
echo "5. Read all JSON event files..."
jn cat 'test_data/events/**/*.json' | \
  jn filter '{event: .event, status: .status, source: ._path}' | \
  jn put output/events.json
echo "   ✓ Created output/events.json"
echo ""

# Example 6: Show path metadata fields
echo "6. Inspect path metadata fields:"
jn cat 'test_data/**/*.jsonl' | jn head -n 1 | jq '{
  _path: ._path,
  _dir: ._dir,
  _filename: ._filename,
  _basename: ._basename,
  _ext: ._ext,
  _file_index: ._file_index,
  _line_index: ._line_index
}'
echo ""

# Show results
echo "=== Results ==="
echo ""
echo "Total log records: $(jq 'length' output/all_logs.json)"
echo "Metrics from compressed file: $(jq 'length' output/metrics.json)"
echo "January log records: $(jq 'length' output/january_logs.json)"
echo "Error records: $(jq 'length' output/errors.json)"
echo "Event records: $(jq 'length' output/events.json)"
echo ""

echo "First error found:"
jq '.[0]' output/errors.json
echo ""

# Cleanup option
if [ "$1" = "--cleanup" ]; then
    echo "Cleaning up..."
    rm -rf test_data output
    echo "Done."
fi

echo "All examples completed! Check output/ directory for results."
echo "Run with --cleanup to remove test data."
