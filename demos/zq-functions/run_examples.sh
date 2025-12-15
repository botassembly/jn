#!/usr/bin/env bash
# =============================================================================
# ZQ Functions Demo
# =============================================================================
#
# This demo showcases ZQ's built-in functions for data transformation.
# ZQ is JN's high-performance filter engine for NDJSON streams.
#
# Categories covered:
# - Generators: Create values (now, epoch, today, xid, nanoid, ulid, uuid7)
# - Transforms: Modify data (keys, values, flatten, unique, sort, reverse)
# - String: Text manipulation (ascii_upcase, ascii_downcase, trim, split, join)
# - Date/Time: Temporal operations (year, month, day, hour, time, weekday)
# - Math: Numerical (abs, exp, ln, log10, sqrt, sin, cos, tan)
# - Case: Naming conventions (snakecase, camelcase, pascalcase, screamcase)
# - ID Time: Extract timestamps from IDs (xid_time, delta, ago)
#
# =============================================================================

set -euo pipefail

ZQ="${ZQ:-zq}"

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
RESET='\033[0m'

demo() {
    echo -e "\n${CYAN}▶ $1${RESET}"
    echo "$ echo '$2' | $ZQ '$3'"
    echo "$2" | $ZQ "$3"
}

demo_raw() {
    echo -e "\n${CYAN}▶ $1${RESET}"
    echo "$ echo '$2' | $ZQ -r '$3'"
    echo "$2" | $ZQ -r "$3"
}

echo "=============================================="
echo "           ZQ Functions Demo"
echo "=============================================="
echo ""
echo "ZQ provides 50+ built-in functions for data"
echo "transformation in NDJSON pipelines."
echo ""

# =============================================================================
# GENERATORS - Create values from nothing
# =============================================================================
echo -e "\n${GREEN}━━━ GENERATORS ━━━${RESET}"

demo_raw "Generate ISO timestamp (UTC)" '{}' 'now'

demo_raw "Generate Unix epoch (seconds)" '{}' 'epoch'

demo_raw "Generate today's date" '{}' 'today'

demo_raw "Generate XID (time-sortable unique ID)" '{}' 'xid'

demo_raw "Generate NanoID (URL-safe random)" '{}' 'nanoid'

demo_raw "Generate ULID (sortable, Crockford base32)" '{}' 'ulid'

demo_raw "Generate UUID v7 (time-based)" '{}' 'uuid7'

# =============================================================================
# TRANSFORMS - Modify data structures
# =============================================================================
echo -e "\n${GREEN}━━━ TRANSFORMS ━━━${RESET}"

demo "Get object keys" '{"name":"Alice","age":30}' 'keys'

demo "Get object values" '{"name":"Alice","age":30}' 'values'

demo "Flatten nested array" '[[1,2],[3,[4,5]]]' 'flatten'

demo "Get unique values" '[1,2,2,3,3,3]' 'unique'

demo "Sort array" '[3,1,4,1,5,9,2,6]' 'sort'

demo "Reverse array" '[1,2,3,4,5]' 'reverse'

demo "Get array length" '[1,2,3,4,5]' 'length'

demo "Get first element" '[10,20,30]' 'first'

demo "Get last element" '[10,20,30]' 'last'

# =============================================================================
# STRING FUNCTIONS
# =============================================================================
echo -e "\n${GREEN}━━━ STRING FUNCTIONS ━━━${RESET}"

demo_raw "Convert to uppercase" '{"text":"hello world"}' '.text | ascii_upcase'

demo_raw "Convert to lowercase" '{"text":"HELLO WORLD"}' '.text | ascii_downcase'

demo_raw "Trim whitespace" '{"text":"  hello  "}' '.text | trim'

demo_raw "Split string" '{"csv":"a,b,c"}' '.csv | split(",")'

demo_raw "Join array to string" '{"parts":["hello","world"]}' '.parts | join(" ")'

demo_raw "Check if starts with" '{"name":"prefix_value"}' '.name | startswith("prefix")'

demo_raw "Check if ends with" '{"name":"value_suffix"}' '.name | endswith("suffix")'

demo_raw "Check if contains" '{"text":"hello world"}' '.text | contains("wor")'

# =============================================================================
# DATE/TIME FUNCTIONS
# =============================================================================
echo -e "\n${GREEN}━━━ DATE/TIME FUNCTIONS ━━━${RESET}"

TIMESTAMP=$(date +%s)
demo_raw "Extract year from timestamp" "{\"ts\":$TIMESTAMP}" '.ts | year'

demo_raw "Extract month (1-12)" "{\"ts\":$TIMESTAMP}" '.ts | month'

demo_raw "Extract day of month" "{\"ts\":$TIMESTAMP}" '.ts | day'

demo_raw "Extract hour (0-23)" "{\"ts\":$TIMESTAMP}" '.ts | hour'

demo_raw "Extract minute" "{\"ts\":$TIMESTAMP}" '.ts | minute'

demo_raw "Extract second" "{\"ts\":$TIMESTAMP}" '.ts | second'

demo_raw "Extract time (HH:MM:SS)" "{\"ts\":$TIMESTAMP}" '.ts | time'

demo_raw "Get ISO week number (1-53)" "{\"ts\":$TIMESTAMP}" '.ts | week'

demo_raw "Get weekday name" "{\"ts\":$TIMESTAMP}" '.ts | weekday'

demo_raw "Get weekday number (0=Sun, 6=Sat)" "{\"ts\":$TIMESTAMP}" '.ts | weekday_num'

# =============================================================================
# MATH FUNCTIONS
# =============================================================================
echo -e "\n${GREEN}━━━ MATH FUNCTIONS ━━━${RESET}"

demo_raw "Absolute value" '{"x":-42}' '.x | abs'

demo_raw "Square root" '{"x":16}' '.x | sqrt'

demo_raw "Natural log" '{"x":2.718281828}' '.x | ln'

demo_raw "Log base 10" '{"x":1000}' '.x | log10'

demo_raw "Log base 2" '{"x":8}' '.x | log2'

demo_raw "Exponential (e^x)" '{"x":1}' '.x | exp'

demo_raw "Floor" '{"x":3.7}' '.x | floor'

demo_raw "Ceil" '{"x":3.2}' '.x | ceil'

demo_raw "Round" '{"x":3.5}' '.x | round'

# =============================================================================
# TRIGONOMETRY
# =============================================================================
echo -e "\n${GREEN}━━━ TRIGONOMETRY ━━━${RESET}"

demo_raw "Sine (radians)" '{"angle":1.5708}' '.angle | sin'

demo_raw "Cosine (radians)" '{"angle":0}' '.angle | cos'

demo_raw "Tangent (radians)" '{"angle":0.7854}' '.angle | tan'

demo_raw "Arc sine" '{"x":1}' '.x | asin'

demo_raw "Arc cosine" '{"x":0}' '.x | acos'

demo_raw "Arc tangent" '{"x":1}' '.x | atan'

# =============================================================================
# CASE CONVERSION
# =============================================================================
echo -e "\n${GREEN}━━━ CASE CONVERSION ━━━${RESET}"

demo_raw "To snake_case" '{"name":"HelloWorld"}' '.name | snakecase'

demo_raw "To camelCase" '{"name":"hello_world"}' '.name | camelcase'

demo_raw "To PascalCase" '{"name":"hello_world"}' '.name | pascalcase'

demo_raw "To SCREAM_CASE" '{"name":"HelloWorld"}' '.name | screamcase'

demo_raw "To kebab-case" '{"name":"HelloWorld"}' '.name | kebabcase'

# =============================================================================
# XID TIME EXTRACTION
# =============================================================================
echo -e "\n${GREEN}━━━ XID TIME EXTRACTION ━━━${RESET}"

# Generate a fresh XID for demo
XID=$($ZQ -r 'xid' <<< '{}')
echo "Using XID: $XID"

demo_raw "Extract timestamp from XID" "{\"id\":\"$XID\"}" '.id | xid_time'

demo_raw "Seconds since XID creation (delta)" "{\"id\":\"$XID\"}" '.id | xid_time | delta'

demo_raw "Human-friendly time since creation (ago)" "{\"id\":\"$XID\"}" '.id | xid_time | ago'

# Wait a moment and show ago working
sleep 2

demo_raw "After 2 seconds, ago shows elapsed time" "{\"id\":\"$XID\"}" '.id | xid_time | ago'

# Show with older timestamp
OLD_TS=$(($(date +%s) - 86400))  # 1 day ago
demo_raw "Ago with timestamp from 1 day ago" "{\"ts\":$OLD_TS}" '.ts | ago'

WEEK_AGO=$(($(date +%s) - 604800))  # 7 days ago
demo_raw "Ago with timestamp from 7 days ago" "{\"ts\":$WEEK_AGO}" '.ts | ago'

# =============================================================================
# CHAINING FUNCTIONS
# =============================================================================
echo -e "\n${GREEN}━━━ CHAINING FUNCTIONS ━━━${RESET}"

demo_raw "Chain multiple transforms" '{"name":"  HELLO world  "}' '.name | trim | ascii_downcase | split(" ") | reverse | join("-")'

demo "Complex object transform" '{"users":[{"name":"alice"},{"name":"bob"}]}' '.users | map(.name | ascii_upcase)'

echo ""
echo "=============================================="
echo "           Demo Complete!"
echo "=============================================="
echo ""
echo "Full function reference: zq --help"
echo ""
echo "Use in pipelines:"
echo "  jn cat data.csv | jn filter '.price | round'"
echo "  jn cat log.jsonl | jn filter '.id | xid_time | ago'"
echo ""
