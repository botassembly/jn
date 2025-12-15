#!/bin/bash
# Folder Profiles Demo - Query JSONL folders with named profiles
#
# Demonstrates:
# - Creating folder profiles for JSONL collections
# - Querying mixed event types with common fields
# - Pre-configured filters in profiles
# - Metadata injection for file tracking
# - Hierarchical profile organization

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Get jn-cat path (from dist or dev build)
if [ -f "../../dist/bin/jn-cat" ]; then
    JN_CAT="../../dist/bin/jn-cat"
    JN_FILTER="../../dist/bin/jn-filter"
elif [ -f "../../tools/zig/jn-cat/bin/jn-cat" ]; then
    JN_CAT="../../tools/zig/jn-cat/bin/jn-cat"
    JN_FILTER="../../tools/zig/jn-filter/bin/jn-filter"
else
    echo "Error: jn-cat not found. Run 'make build' or 'make tool-jn-cat' first."
    exit 1
fi

echo "=== JN Folder Profiles Demo ==="
echo ""

# Create test data directory structure
echo "Setting up test data..."
rm -rf test_data .jn output
mkdir -p test_data/events/2024-01 test_data/events/2024-02
mkdir -p test_data/metrics/server1 test_data/metrics/server2
mkdir -p .jn/profiles/file/events
mkdir -p .jn/profiles/file/metrics
mkdir -p output

# ============================================================================
# Create test JSONL files with different event types
# ============================================================================

# User events (login, logout)
cat > test_data/events/2024-01/users.jsonl << 'EOF'
{"timestamp": "2024-01-15T10:00:00Z", "event_type": "login", "user_id": "user123", "ip": "192.168.1.1"}
{"timestamp": "2024-01-15T10:30:00Z", "event_type": "logout", "user_id": "user123", "session_duration": 1800}
{"timestamp": "2024-01-15T11:00:00Z", "event_type": "login", "user_id": "user456", "ip": "192.168.1.2"}
EOF

# Order events (created, shipped, delivered)
cat > test_data/events/2024-01/orders.jsonl << 'EOF'
{"timestamp": "2024-01-15T09:00:00Z", "event_type": "order_created", "order_id": "ORD001", "user_id": "user123", "total": 99.99}
{"timestamp": "2024-01-15T14:00:00Z", "event_type": "order_shipped", "order_id": "ORD001", "carrier": "UPS"}
{"timestamp": "2024-01-16T10:00:00Z", "event_type": "order_delivered", "order_id": "ORD001"}
EOF

# More events in February
cat > test_data/events/2024-02/users.jsonl << 'EOF'
{"timestamp": "2024-02-01T08:00:00Z", "event_type": "login", "user_id": "user789", "ip": "10.0.0.1"}
{"timestamp": "2024-02-01T12:00:00Z", "event_type": "login", "user_id": "user123", "ip": "192.168.1.1"}
{"timestamp": "2024-02-01T18:00:00Z", "event_type": "logout", "user_id": "user123", "session_duration": 21600}
EOF

cat > test_data/events/2024-02/orders.jsonl << 'EOF'
{"timestamp": "2024-02-01T10:00:00Z", "event_type": "order_created", "order_id": "ORD002", "user_id": "user789", "total": 149.99}
{"timestamp": "2024-02-02T09:00:00Z", "event_type": "order_shipped", "order_id": "ORD002", "carrier": "FedEx"}
EOF

# System errors (mixed in with events)
cat > test_data/events/2024-01/errors.jsonl << 'EOF'
{"timestamp": "2024-01-15T10:05:00Z", "event_type": "error", "level": "ERROR", "message": "Database connection failed", "service": "api"}
{"timestamp": "2024-01-15T15:30:00Z", "event_type": "error", "level": "WARN", "message": "Rate limit exceeded", "service": "api", "user_id": "user456"}
EOF

# Metrics data (different schema entirely)
cat > test_data/metrics/server1/cpu.jsonl << 'EOF'
{"timestamp": "2024-01-15T10:00:00Z", "metric": "cpu_usage", "value": 45.2, "host": "server1"}
{"timestamp": "2024-01-15T10:01:00Z", "metric": "cpu_usage", "value": 52.1, "host": "server1"}
{"timestamp": "2024-01-15T10:02:00Z", "metric": "cpu_usage", "value": 48.7, "host": "server1"}
EOF

cat > test_data/metrics/server1/memory.jsonl << 'EOF'
{"timestamp": "2024-01-15T10:00:00Z", "metric": "memory_pct", "value": 78.5, "host": "server1"}
{"timestamp": "2024-01-15T10:01:00Z", "metric": "memory_pct", "value": 79.2, "host": "server1"}
EOF

cat > test_data/metrics/server2/cpu.jsonl << 'EOF'
{"timestamp": "2024-01-15T10:00:00Z", "metric": "cpu_usage", "value": 32.1, "host": "server2"}
{"timestamp": "2024-01-15T10:01:00Z", "metric": "cpu_usage", "value": 35.8, "host": "server2"}
EOF

echo "   Created test data in test_data/"
echo ""

# ============================================================================
# Create folder profiles
# ============================================================================

# Base config for events namespace
cat > .jn/profiles/file/events/_meta.json << 'EOF'
{
  "description": "Event log profiles",
  "inject_meta": true
}
EOF

# All events profile
cat > .jn/profiles/file/events/all.json << 'EOF'
{
  "pattern": "test_data/events/**/*.jsonl",
  "description": "All events across all months and types"
}
EOF

# User events only
cat > .jn/profiles/file/events/users.json << 'EOF'
{
  "pattern": "test_data/events/**/*.jsonl",
  "filter": "select(.event_type == \"login\" or .event_type == \"logout\")",
  "description": "User login/logout events only"
}
EOF

# Logins only
cat > .jn/profiles/file/events/logins.json << 'EOF'
{
  "pattern": "test_data/events/**/*.jsonl",
  "filter": "select(.event_type == \"login\")",
  "description": "Login events only"
}
EOF

# Order events only
cat > .jn/profiles/file/events/orders.json << 'EOF'
{
  "pattern": "test_data/events/**/*.jsonl",
  "filter": "select(.event_type | startswith(\"order_\"))",
  "description": "Order-related events"
}
EOF

# Errors only
cat > .jn/profiles/file/events/errors.json << 'EOF'
{
  "pattern": "test_data/events/**/*.jsonl",
  "filter": "select(.event_type == \"error\")",
  "description": "Error events only"
}
EOF

# January events
cat > .jn/profiles/file/events/january.json << 'EOF'
{
  "pattern": "test_data/events/2024-01/**/*.jsonl",
  "description": "All January 2024 events"
}
EOF

# Metrics profiles
cat > .jn/profiles/file/metrics/_meta.json << 'EOF'
{
  "description": "Server metrics profiles",
  "inject_meta": true
}
EOF

cat > .jn/profiles/file/metrics/all.json << 'EOF'
{
  "pattern": "test_data/metrics/**/*.jsonl",
  "description": "All server metrics"
}
EOF

cat > .jn/profiles/file/metrics/cpu.json << 'EOF'
{
  "pattern": "test_data/metrics/**/*.jsonl",
  "filter": "select(.metric == \"cpu_usage\")",
  "description": "CPU usage metrics only"
}
EOF

cat > .jn/profiles/file/metrics/high_cpu.json << 'EOF'
{
  "pattern": "test_data/metrics/**/*.jsonl",
  "filter": "select(.metric == \"cpu_usage\" and .value > 50)",
  "description": "High CPU usage (>50%)"
}
EOF

echo "   Created folder profiles in .jn/profiles/file/"
echo ""

# ============================================================================
# Run examples
# ============================================================================

echo "1. Query all events with @events/all..."
$JN_CAT '@events/all' 2>/dev/null | head -5 > output/all_events.jsonl
echo "   First 5 records saved to output/all_events.jsonl"
echo ""

echo "2. Query login events only with @events/logins..."
$JN_CAT '@events/logins' 2>/dev/null > output/logins.jsonl
echo "   $(wc -l < output/logins.jsonl) login events saved to output/logins.jsonl"
echo ""

echo "3. Query order events with @events/orders..."
$JN_CAT '@events/orders' 2>/dev/null > output/orders.jsonl
echo "   $(wc -l < output/orders.jsonl) order events saved to output/orders.jsonl"
echo ""

echo "4. Query January events only with @events/january..."
$JN_CAT '@events/january' 2>/dev/null > output/january.jsonl
echo "   $(wc -l < output/january.jsonl) January events saved to output/january.jsonl"
echo ""

echo "5. Query CPU metrics with @metrics/cpu..."
$JN_CAT '@metrics/cpu' 2>/dev/null > output/cpu_metrics.jsonl
echo "   $(wc -l < output/cpu_metrics.jsonl) CPU metrics saved to output/cpu_metrics.jsonl"
echo ""

echo "6. Query high CPU (>50%) with @metrics/high_cpu..."
$JN_CAT '@metrics/high_cpu' 2>/dev/null > output/high_cpu.jsonl
echo "   $(wc -l < output/high_cpu.jsonl) high CPU records saved to output/high_cpu.jsonl"
echo ""

echo "7. Query errors with @events/errors..."
$JN_CAT '@events/errors' 2>/dev/null > output/errors.jsonl
echo "   $(wc -l < output/errors.jsonl) errors saved to output/errors.jsonl"
echo ""

# ============================================================================
# Show sample output
# ============================================================================

echo "=== Sample Output ==="
echo ""
echo "Login events (with path metadata):"
head -2 output/logins.jsonl | jq -c '{event: .event_type, user: .user_id, file: ._filename}'
echo ""

echo "Order events:"
head -2 output/orders.jsonl | jq -c '{event: .event_type, order: .order_id, file: ._filename}'
echo ""

echo "High CPU alerts:"
cat output/high_cpu.jsonl | jq -c '{host: .host, value: .value, file: ._filename}'
echo ""

# ============================================================================
# Show profile structure
# ============================================================================

echo "=== Profile Structure ==="
echo ""
echo "Profiles are stored at .jn/profiles/file/<namespace>/<name>.json"
echo ""
tree .jn/profiles/file/ 2>/dev/null || find .jn/profiles/file -type f | sort
echo ""

echo "=== Example Profile (events/logins.json) ==="
cat .jn/profiles/file/events/logins.json | jq .
echo ""

# Cleanup option
if [ "$1" = "--cleanup" ]; then
    echo "Cleaning up..."
    rm -rf test_data .jn output
    echo "Done."
fi

echo "All examples completed! Check output/ directory for results."
echo "Run with --cleanup to remove test data."
