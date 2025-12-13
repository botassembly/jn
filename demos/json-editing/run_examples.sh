#!/bin/bash
# JSON Editing Demo - jn-edit tool
#
# jn-edit provides surgical JSON editing with three modes:
# 1. Path Assignment: .path=value (strings) or .path:=value (raw JSON)
# 2. Merge Patch: --merge '{"key": "value"}' overlays JSON
# 3. Delete: --del .path removes fields
#
# Key features:
# - Preserves structure (doesn't re-serialize entire file)
# - Works on both single JSON and NDJSON streams
# - Explicit operations (no magic null deletion)

set -e
cd "$(dirname "$0")"

# Resolve jn-edit path (from build output or PATH)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
JN_EDIT="${SCRIPT_DIR}/../../tools/zig/jn-edit/bin/jn-edit"
if [ ! -x "$JN_EDIT" ]; then
    JN_EDIT="jn-edit"  # Fall back to PATH
fi

# Helper to convert multi-line JSON to NDJSON for jn-edit
to_ndjson() {
    tr -d '\n' | sed 's/  */ /g'
}

echo "=== JSON Editing Demo ==="
echo ""

# ---------------------------------------------------------------------------
# PART 1: Path Assignment (Simple key=value)
# ---------------------------------------------------------------------------

echo "--- Part 1: Path Assignment ---"
echo ""

echo "# Original JSON:"
cat sample.json
echo ""

echo "# Set a string value: .name=Bob"
cat sample.json | to_ndjson | $JN_EDIT .name=Bob
echo ""

echo "# Set a number (use := for raw JSON): .age:=25"
cat sample.json | to_ndjson | $JN_EDIT .age:=25
echo ""

echo "# Set a boolean: .active:=false"
cat sample.json | to_ndjson | $JN_EDIT .active:=false
echo ""

echo "# Set nested path: .profile.location=Boston"
cat sample.json | to_ndjson | $JN_EDIT .profile.location=Boston
echo ""

echo "# Multiple edits at once: .name=Charlie .age:=35 .profile.location=LA"
cat sample.json | to_ndjson | $JN_EDIT .name=Charlie .age:=35 .profile.location=LA
echo ""

echo "# Set array element: .tags[0]=engineer"
cat sample.json | to_ndjson | $JN_EDIT '.tags[0]=engineer'
echo ""

echo "# Set null value: .email:=null"
cat sample.json | to_ndjson | $JN_EDIT .email:=null
echo ""

# ---------------------------------------------------------------------------
# PART 2: Delete Operations
# ---------------------------------------------------------------------------

echo "--- Part 2: Delete Operations ---"
echo ""

echo "# Delete a field: --del .email"
cat sample.json | to_ndjson | $JN_EDIT --del .email
echo ""

echo "# Delete nested field: --del .profile.bio"
cat sample.json | to_ndjson | $JN_EDIT --del .profile.bio
echo ""

echo "# Delete multiple fields: --del .email --del .settings"
cat sample.json | to_ndjson | $JN_EDIT --del .email --del .settings
echo ""

echo "# Combined set and delete: .name=Bob --del .email"
cat sample.json | to_ndjson | $JN_EDIT .name=Bob --del .email
echo ""

# ---------------------------------------------------------------------------
# PART 3: Merge Patch (RFC 7396 style)
# ---------------------------------------------------------------------------

echo "--- Part 3: Merge Patch ---"
echo ""

echo '# Merge partial JSON: --merge {"name":"Eve","age":28}'
cat sample.json | to_ndjson | $JN_EDIT --merge '{"name": "Eve", "age": 28}'
echo ""

echo '# Merge nested: --merge {"profile":{"bio":"Designer"}}'
cat sample.json | to_ndjson | $JN_EDIT --merge '{"profile": {"bio": "Designer"}}'
echo ""

echo '# Add new fields via merge: --merge {"newField":"hello"}'
cat sample.json | to_ndjson | $JN_EDIT --merge '{"newField": "hello", "count": 42}'
echo ""

# ---------------------------------------------------------------------------
# PART 4: Array Operations
# ---------------------------------------------------------------------------

echo "--- Part 4: Array Operations ---"
echo ""

echo "# Append to array: --append .tags moderator"
cat sample.json | to_ndjson | $JN_EDIT --append .tags moderator
echo ""

echo "# Prepend to array: --prepend .tags owner"
cat sample.json | to_ndjson | $JN_EDIT --prepend .tags owner
echo ""

# ---------------------------------------------------------------------------
# PART 5: NDJSON Stream Editing
# ---------------------------------------------------------------------------

echo "--- Part 5: NDJSON Stream Editing ---"
echo ""

echo "# Original NDJSON:"
cat users.ndjson
echo ""

echo "# Edit all records: .active:=true"
cat users.ndjson | $JN_EDIT .active:=true
echo ""

echo "# Add field to all: .verified:=false"
cat users.ndjson | $JN_EDIT .verified:=false
echo ""

echo "# Delete field from all: --del .role"
cat users.ndjson | $JN_EDIT --del .role
echo ""

# ---------------------------------------------------------------------------
# PART 6: Create Nested Paths
# ---------------------------------------------------------------------------

echo "--- Part 6: Create Nested Paths ---"
echo ""

echo "# Path doesn't exist (creates it): .new.nested.path=value"
echo '{}' | $JN_EDIT .new.nested.path=value
echo ""

echo "# Create deeply nested structure from empty object:"
echo '{}' | $JN_EDIT .user.profile.settings.theme=dark
echo ""

echo "=== Demo Complete ==="
