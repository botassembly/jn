#!/usr/bin/env bash
# =============================================================================
# JN Grep Demo - Line-based Text Filtering with NDJSON
# =============================================================================
#
# This demo shows how to use jn-sh and zq for grep-like text processing
# with structured JSON output including line numbers.
#
# Key components:
#   jn-sh --raw <cmd>  Convert command output to NDJSON: {"line": N, "text": "..."}
#   zq                 Filter and transform the NDJSON stream
#
# =============================================================================

set -euo pipefail

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RESET='\033[0m'

demo() {
    echo -e "\n${CYAN}▶ $1${RESET}"
    echo -e "${YELLOW}\$ $2${RESET}"
    eval "$2"
}

echo "=============================================="
echo "     JN Grep - Structured Text Search"
echo "=============================================="
echo ""
echo "Convert any text to NDJSON with line numbers,"
echo "then filter with ZQ's powerful expressions."
echo ""

# Create sample files
SAMPLE_DIR=$(mktemp -d)
trap "rm -rf $SAMPLE_DIR" EXIT

cat > "$SAMPLE_DIR/app.log" << 'EOF'
2024-12-15 10:00:01 INFO Starting application
2024-12-15 10:00:02 DEBUG Loading configuration
2024-12-15 10:00:03 INFO Database connected
2024-12-15 10:00:05 WARN High memory usage detected
2024-12-15 10:00:10 ERROR Failed to connect to cache server
2024-12-15 10:00:11 INFO Retrying cache connection
2024-12-15 10:00:15 ERROR Cache connection timeout
2024-12-15 10:00:20 INFO Application ready
2024-12-15 10:01:00 DEBUG Processing request from user-123
2024-12-15 10:01:01 INFO Request completed successfully
EOF

cat > "$SAMPLE_DIR/config.ini" << 'EOF'
[database]
host = localhost
port = 5432
name = myapp

[cache]
host = redis.local
port = 6379
timeout = 30

[logging]
level = DEBUG
format = json
EOF

cat > "$SAMPLE_DIR/users.txt" << 'EOF'
alice:1001:Engineering:alice@example.com
bob:1002:Marketing:bob@example.com
charlie:1003:Engineering:charlie@example.com
diana:1004:Sales:diana@example.com
eve:1005:Engineering:eve@example.com
EOF

# =============================================================================
echo -e "\n${GREEN}━━━ BASIC TEXT SEARCH ━━━${RESET}"
# =============================================================================

demo "Convert text to NDJSON with line numbers" \
    "jn-sh --raw cat $SAMPLE_DIR/app.log | head -3"

demo "Search for 'ERROR' lines (like grep ERROR)" \
    "jn-sh --raw cat $SAMPLE_DIR/app.log | zq 'select(.text | contains(\"ERROR\"))'"

demo "Case-insensitive search for 'error'" \
    "jn-sh --raw cat $SAMPLE_DIR/app.log | zq 'select(.text | ascii_downcase | contains(\"error\"))'"

# =============================================================================
echo -e "\n${GREEN}━━━ PATTERN MATCHING ━━━${RESET}"
# =============================================================================

demo "Lines starting with a pattern (like grep ^)" \
    "jn-sh --raw cat $SAMPLE_DIR/app.log | zq 'select(.text | startswith(\"2024-12-15 10:00\"))'"

demo "Lines containing 'INFO' or 'WARN'" \
    "jn-sh --raw cat $SAMPLE_DIR/app.log | zq 'select((.text | contains(\"INFO\")) or (.text | contains(\"WARN\")))'"

demo "Lines NOT containing 'DEBUG'" \
    "jn-sh --raw cat $SAMPLE_DIR/app.log | zq 'select(not (.text | contains(\"DEBUG\")))'"

# =============================================================================
echo -e "\n${GREEN}━━━ EXTRACT LINE NUMBERS ━━━${RESET}"
# =============================================================================

demo "Get just the line numbers of errors" \
    "jn-sh --raw cat $SAMPLE_DIR/app.log | zq -r 'select(.text | contains(\"ERROR\")) | .line'"

demo "Format as 'line:text' (like grep -n)" \
    "jn-sh --raw cat $SAMPLE_DIR/app.log | zq 'select(.text | contains(\"ERROR\"))' | zq -r '(.line | tostring) + \":\" + .text'"

# =============================================================================
echo -e "\n${GREEN}━━━ CONFIG FILE PARSING ━━━${RESET}"
# =============================================================================

demo "Find all lines with 'host'" \
    "jn-sh --raw cat $SAMPLE_DIR/config.ini | zq 'select(.text | contains(\"host\"))'"

demo "Skip empty lines and comments" \
    "jn-sh --raw cat $SAMPLE_DIR/config.ini | zq 'select(.text | length > 0) | select(not (.text | startswith(\"[\")))'  | head -5"

# =============================================================================
echo -e "\n${GREEN}━━━ DELIMITED DATA ━━━${RESET}"
# =============================================================================

demo "Parse colon-delimited file" \
    "jn-sh --raw cat $SAMPLE_DIR/users.txt | zq '{line, user: (.text | split(\":\") | first), dept: (.text | split(\":\") | .[2])}'"

demo "Filter Engineering department" \
    "jn-sh --raw cat $SAMPLE_DIR/users.txt | zq 'select(.text | contains(\":Engineering:\"))'"

# =============================================================================
echo -e "\n${GREEN}━━━ COUNT AND STATS ━━━${RESET}"
# =============================================================================

demo "Count lines matching pattern" \
    "jn-sh --raw cat $SAMPLE_DIR/app.log | zq 'select(.text | contains(\"ERROR\"))' | zq -s 'length'"

demo "Count total lines (like wc -l)" \
    "jn-sh --raw cat $SAMPLE_DIR/app.log | zq -s 'length'"

# =============================================================================
echo -e "\n${GREEN}━━━ CHAINING WITH OTHER TOOLS ━━━${RESET}"
# =============================================================================

demo "Pipe through standard tools" \
    "jn-sh --raw cat $SAMPLE_DIR/app.log | zq -r 'select(.text | contains(\"ERROR\")) | .text' | wc -l"

demo "Output as JSON array for further processing" \
    "jn-sh --raw cat $SAMPLE_DIR/app.log | zq 'select(.text | contains(\"ERROR\"))' | zq -s '.'"

echo ""
echo "=============================================="
echo "           Demo Complete!"
echo "=============================================="
echo ""
echo "Key patterns:"
echo "  jn-sh --raw cat FILE | zq 'select(.text | contains(\"PATTERN\"))'"
echo "  jn-sh --raw COMMAND  | zq 'select(.text | startswith(\"PREFIX\"))'"
echo "  jn-sh --raw cat FILE | zq -r '.line'  # Line numbers only"
echo ""
echo "Works with any command output:"
echo "  jn-sh --raw ps aux | zq 'select(.text | contains(\"python\"))'"
echo "  jn-sh --raw dmesg  | zq 'select(.text | contains(\"error\"))'"
echo ""
