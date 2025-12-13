#!/bin/bash
#
# =============================================================================
# jn-edit: Surgical JSON Editing for Command Line Workflows
# =============================================================================
#
# PROBLEM STATEMENT
# -----------------
# Editing JSON from the command line is surprisingly hard:
#
# 1. jq is a FILTER, not an editor - it reads, transforms, and outputs
#    You can't do: jq '.name = "Bob"' file.json  (this doesn't modify the file)
#    You must do:  jq '.name = "Bob"' file.json > tmp && mv tmp file.json
#
# 2. jq re-serializes the entire document
#    - Your carefully formatted JSON becomes compact one-liner
#    - Comments (in JSONC) are lost
#    - Key order may change
#
# 3. Trailing comma problems
#    - JSON doesn't allow trailing commas: {"a": 1,}  <-- INVALID
#    - Easy to introduce when manually editing
#
# 4. Quoting hell
#    - Shell quoting + JSON quoting = nightmare
#    - jq '.key = "value with \"quotes\""' file.json
#
# SOLUTION: jn-edit
# -----------------
# A purpose-built tool for surgical JSON edits:
#
#   - Simple path=value syntax (inspired by HTTPie)
#   - Explicit operations (set, delete, merge, append)
#   - Works on NDJSON streams (one JSON object per line)
#   - No magic behaviors (like RFC 7396's null-means-delete)
#
# =============================================================================
# SYNTAX REFERENCE
# =============================================================================
#
# PATH ASSIGNMENT (the 80% use case):
#
#   .path=value       Set path to STRING value
#   .path:=value      Set path to RAW JSON value (number, bool, null, object)
#
#   The := syntax is borrowed from HTTPie. It means "interpret as JSON, not string"
#
#   Examples:
#     .name=Alice           -> {"name": "Alice"}         (string)
#     .age:=30              -> {"age": 30}               (number)
#     .active:=true         -> {"active": true}          (boolean)
#     .data:=null           -> {"data": null}            (null)
#     .config:='{"a":1}'    -> {"config": {"a": 1}}      (object)
#
# NESTED PATHS:
#
#   .user.name=Alice        Creates intermediate objects automatically
#   .tags[0]=first          Array index syntax for element access
#
# DELETE OPERATIONS:
#
#   --del .path             Remove a field from the object
#
#   Why explicit --del instead of .path:=null?
#   - Setting to null and deleting are different operations
#   - RFC 7396 uses null-means-delete, which surprises many users
#   - Explicit is better than implicit
#
# MERGE PATCH (RFC 7396 style):
#
#   --merge '{"key": "value"}'
#
#   Recursively merges the patch object into the target:
#   - New keys are added
#   - Existing keys are overwritten
#   - Nested objects are merged recursively
#
#   When to use merge vs path assignment:
#   - Path assignment: single field changes, simple edits
#   - Merge: updating multiple nested fields at once
#
# ARRAY OPERATIONS:
#
#   --append .path value    Add to end of array
#   --prepend .path value   Add to beginning of array
#
#   Note: RFC 7396 Merge Patch CANNOT append to arrays - it can only
#   replace them entirely. These operations fill that gap.
#
# =============================================================================
# NDJSON: THE UNIVERSAL INTERCHANGE FORMAT
# =============================================================================
#
# jn-edit works on NDJSON (Newline Delimited JSON):
#
#   {"id": 1, "name": "Alice"}
#   {"id": 2, "name": "Bob"}
#   {"id": 3, "name": "Carol"}
#
# Why NDJSON?
#
# 1. STREAMABLE - Process gigabytes without loading into memory
# 2. UNIX-FRIENDLY - One record per line, works with head/tail/grep
# 3. RECOVERABLE - A corrupt line doesn't invalidate the whole file
# 4. APPENDABLE - Just append a line, no need to parse/rewrite
#
# Converting pretty JSON to NDJSON:
#
#   # Multi-line object -> single line
#   cat pretty.json | jq -c '.'
#
#   # JSON array -> NDJSON stream
#   cat array.json | jq -c '.[]'
#
# =============================================================================

set -e
cd "$(dirname "$0")"

# -----------------------------------------------------------------------------
# SETUP: Locate jn-edit binary
# -----------------------------------------------------------------------------
# Try the local build first, fall back to PATH for installed version

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
JN_EDIT="${SCRIPT_DIR}/../../tools/zig/jn-edit/bin/jn-edit"
if [ ! -x "$JN_EDIT" ]; then
    JN_EDIT="jn-edit"
fi

# -----------------------------------------------------------------------------
# HELPER: Convert pretty-printed JSON to NDJSON
# -----------------------------------------------------------------------------
# jn-edit expects NDJSON input. This helper collapses multi-line JSON
# into a single line suitable for processing.
#
# For production use, prefer: jq -c '.' or store data as NDJSON

to_ndjson() {
    tr -d '\n' | sed 's/  */ /g'
}

# =============================================================================
echo "=============================================================================
jn-edit Demo: Surgical JSON Editing
============================================================================="
echo ""

# =============================================================================
# PART 1: PATH ASSIGNMENT - The Most Common Operation
# =============================================================================
#
# Most JSON edits are simple: "change field X to value Y"
# jn-edit makes this trivial with the .path=value syntax.

echo "-----------------------------------------------------------------------------"
echo "PART 1: Path Assignment (Simple Field Updates)"
echo "-----------------------------------------------------------------------------"
echo ""

# Show the original data we'll be editing
echo "SAMPLE DATA (sample.json):"
echo ""
cat sample.json
echo ""
echo ""

# ---------------------------------------------------------------------------
# String values: Use = for string assignment
# ---------------------------------------------------------------------------
# The value after = is treated as a string literal.
# No quotes needed - the tool handles JSON string escaping.

echo "EXAMPLE 1.1: Set a string value"
echo "Command: jn-edit .name=Bob"
echo "Result:"
cat sample.json | to_ndjson | $JN_EDIT .name=Bob
echo ""
echo ""

# ---------------------------------------------------------------------------
# Numeric values: Use := for raw JSON
# ---------------------------------------------------------------------------
# The := operator means "interpret as JSON, not as a string"
# This is essential for numbers, booleans, null, arrays, and objects.
#
# Without :=, the value 25 would become the STRING "25", not the NUMBER 25

echo "EXAMPLE 1.2: Set a numeric value"
echo "Command: jn-edit .age:=25"
echo "Note: := means 'raw JSON value', not string"
echo "Result:"
cat sample.json | to_ndjson | $JN_EDIT .age:=25
echo ""
echo ""

# ---------------------------------------------------------------------------
# Boolean values: Also use :=
# ---------------------------------------------------------------------------

echo "EXAMPLE 1.3: Set a boolean value"
echo "Command: jn-edit .active:=false"
echo "Result:"
cat sample.json | to_ndjson | $JN_EDIT .active:=false
echo ""
echo ""

# ---------------------------------------------------------------------------
# Nested paths: Dot notation traverses objects
# ---------------------------------------------------------------------------
# jn-edit automatically navigates nested structures.
# If intermediate objects don't exist, they're created.

echo "EXAMPLE 1.4: Set a nested field"
echo "Command: jn-edit .profile.location=Boston"
echo "Result:"
cat sample.json | to_ndjson | $JN_EDIT .profile.location=Boston
echo ""
echo ""

# ---------------------------------------------------------------------------
# Multiple edits: Chain multiple assignments in one call
# ---------------------------------------------------------------------------
# More efficient than piping through multiple jn-edit calls.
# All edits are applied to each record in order.

echo "EXAMPLE 1.5: Multiple edits in one command"
echo "Command: jn-edit .name=Charlie .age:=35 .profile.location=LA"
echo "Result:"
cat sample.json | to_ndjson | $JN_EDIT .name=Charlie .age:=35 .profile.location=LA
echo ""
echo ""

# ---------------------------------------------------------------------------
# Array index: Access specific elements with [N] syntax
# ---------------------------------------------------------------------------
# Arrays are zero-indexed. If the index is beyond the array length,
# the array is automatically extended with null values.

echo "EXAMPLE 1.6: Set an array element by index"
echo "Command: jn-edit '.tags[0]=engineer'"
echo "Note: Quotes needed to prevent shell glob expansion of []"
echo "Result:"
cat sample.json | to_ndjson | $JN_EDIT '.tags[0]=engineer'
echo ""
echo ""

# ---------------------------------------------------------------------------
# Setting null: Use := with the literal null
# ---------------------------------------------------------------------------
# Important: This SETS the field to null, it does NOT delete it.
# To delete a field, use --del (see Part 2).

echo "EXAMPLE 1.7: Set a field to null"
echo "Command: jn-edit .email:=null"
echo "Note: This sets to null, NOT deletes. Use --del to delete."
echo "Result:"
cat sample.json | to_ndjson | $JN_EDIT .email:=null
echo ""
echo ""

# =============================================================================
# PART 2: DELETE OPERATIONS - Removing Fields
# =============================================================================
#
# RFC 7396 (JSON Merge Patch) uses null to mean "delete this field".
# This is surprising to many users who expect null to mean... null.
#
# jn-edit uses explicit --del for clarity:
#   .field:=null  -> sets field to null value
#   --del .field  -> removes field entirely

echo "-----------------------------------------------------------------------------"
echo "PART 2: Delete Operations (Removing Fields)"
echo "-----------------------------------------------------------------------------"
echo ""

# ---------------------------------------------------------------------------
# Basic delete: Remove a top-level field
# ---------------------------------------------------------------------------

echo "EXAMPLE 2.1: Delete a field"
echo "Command: jn-edit --del .email"
echo "Result:"
cat sample.json | to_ndjson | $JN_EDIT --del .email
echo ""
echo ""

# ---------------------------------------------------------------------------
# Nested delete: Remove a field from a nested object
# ---------------------------------------------------------------------------

echo "EXAMPLE 2.2: Delete a nested field"
echo "Command: jn-edit --del .profile.bio"
echo "Result:"
cat sample.json | to_ndjson | $JN_EDIT --del .profile.bio
echo ""
echo ""

# ---------------------------------------------------------------------------
# Multiple deletes: Remove several fields at once
# ---------------------------------------------------------------------------

echo "EXAMPLE 2.3: Delete multiple fields"
echo "Command: jn-edit --del .email --del .settings"
echo "Result:"
cat sample.json | to_ndjson | $JN_EDIT --del .email --del .settings
echo ""
echo ""

# ---------------------------------------------------------------------------
# Mixed operations: Combine set and delete
# ---------------------------------------------------------------------------
# Order matters: operations are applied left-to-right

echo "EXAMPLE 2.4: Combine set and delete"
echo "Command: jn-edit .name=Bob --del .email"
echo "Result:"
cat sample.json | to_ndjson | $JN_EDIT .name=Bob --del .email
echo ""
echo ""

# =============================================================================
# PART 3: MERGE PATCH - Bulk Updates via JSON Overlay
# =============================================================================
#
# When you need to update multiple nested fields, merge patch is cleaner
# than multiple path assignments.
#
# Merge semantics (RFC 7396):
#   - Scalar values: overwrite
#   - Objects: merge recursively
#   - Arrays: overwrite entirely (no element-wise merge)
#
# Note: jn-edit does NOT use null-means-delete from RFC 7396.
# Use --del for deletions.

echo "-----------------------------------------------------------------------------"
echo "PART 3: Merge Patch (Bulk Updates)"
echo "-----------------------------------------------------------------------------"
echo ""

# ---------------------------------------------------------------------------
# Basic merge: Overlay a partial object
# ---------------------------------------------------------------------------

echo 'EXAMPLE 3.1: Merge a partial object'
echo 'Command: jn-edit --merge '\''{"name": "Eve", "age": 28}'\'
echo "Result:"
cat sample.json | to_ndjson | $JN_EDIT --merge '{"name": "Eve", "age": 28}'
echo ""
echo ""

# ---------------------------------------------------------------------------
# Nested merge: Updates are applied recursively
# ---------------------------------------------------------------------------
# The patch {"profile": {"bio": "Designer"}} merges into the existing
# profile object, only updating the bio field while preserving location, etc.

echo 'EXAMPLE 3.2: Merge nested objects (recursive)'
echo 'Command: jn-edit --merge '\''{"profile": {"bio": "Designer"}}'\'
echo "Note: Only bio is changed; location and social are preserved"
echo "Result:"
cat sample.json | to_ndjson | $JN_EDIT --merge '{"profile": {"bio": "Designer"}}'
echo ""
echo ""

# ---------------------------------------------------------------------------
# Add new fields: Merge can introduce new keys
# ---------------------------------------------------------------------------

echo 'EXAMPLE 3.3: Add new fields via merge'
echo 'Command: jn-edit --merge '\''{"newField": "hello", "count": 42}'\'
echo "Result:"
cat sample.json | to_ndjson | $JN_EDIT --merge '{"newField": "hello", "count": 42}'
echo ""
echo ""

# =============================================================================
# PART 4: ARRAY OPERATIONS - Append and Prepend
# =============================================================================
#
# RFC 7396 Merge Patch has a known limitation: it cannot append to arrays.
# A merge with {"tags": ["new"]} would REPLACE the entire tags array.
#
# jn-edit provides explicit --append and --prepend operations:

echo "-----------------------------------------------------------------------------"
echo "PART 4: Array Operations (Append/Prepend)"
echo "-----------------------------------------------------------------------------"
echo ""

# ---------------------------------------------------------------------------
# Append: Add to the end of an array
# ---------------------------------------------------------------------------

echo "EXAMPLE 4.1: Append to an array"
echo "Command: jn-edit --append .tags moderator"
echo "Before: [\"developer\", \"admin\"]"
echo "After:  [\"developer\", \"admin\", \"moderator\"]"
echo "Result:"
cat sample.json | to_ndjson | $JN_EDIT --append .tags moderator
echo ""
echo ""

# ---------------------------------------------------------------------------
# Prepend: Add to the beginning of an array
# ---------------------------------------------------------------------------

echo "EXAMPLE 4.2: Prepend to an array"
echo "Command: jn-edit --prepend .tags owner"
echo "Before: [\"developer\", \"admin\"]"
echo "After:  [\"owner\", \"developer\", \"admin\"]"
echo "Result:"
cat sample.json | to_ndjson | $JN_EDIT --prepend .tags owner
echo ""
echo ""

# =============================================================================
# PART 5: NDJSON STREAM EDITING - Batch Processing
# =============================================================================
#
# jn-edit shines when processing NDJSON streams. Each line is edited
# independently, making it perfect for:
#
#   - Batch updates to database exports
#   - Log file transformations
#   - API response post-processing
#   - ETL pipelines

echo "-----------------------------------------------------------------------------"
echo "PART 5: NDJSON Stream Editing (Batch Processing)"
echo "-----------------------------------------------------------------------------"
echo ""

echo "SAMPLE DATA (users.ndjson):"
echo ""
cat users.ndjson
echo ""
echo ""

# ---------------------------------------------------------------------------
# Batch update: Apply same edit to all records
# ---------------------------------------------------------------------------

echo "EXAMPLE 5.1: Edit all records in a stream"
echo "Command: cat users.ndjson | jn-edit .active:=true"
echo "Result:"
cat users.ndjson | $JN_EDIT .active:=true
echo ""
echo ""

# ---------------------------------------------------------------------------
# Add field to all: Useful for data enrichment
# ---------------------------------------------------------------------------

echo "EXAMPLE 5.2: Add a new field to all records"
echo "Command: cat users.ndjson | jn-edit .verified:=false"
echo "Result:"
cat users.ndjson | $JN_EDIT .verified:=false
echo ""
echo ""

# ---------------------------------------------------------------------------
# Remove field from all: Data sanitization
# ---------------------------------------------------------------------------

echo "EXAMPLE 5.3: Remove a field from all records"
echo "Command: cat users.ndjson | jn-edit --del .role"
echo "Result:"
cat users.ndjson | $JN_EDIT --del .role
echo ""
echo ""

# =============================================================================
# PART 6: AUTOMATIC PATH CREATION - Building Structure from Nothing
# =============================================================================
#
# Unlike jq which requires paths to exist, jn-edit creates intermediate
# objects automatically. This is useful for:
#
#   - Initializing config files
#   - Building objects incrementally
#   - Setting deeply nested values without boilerplate

echo "-----------------------------------------------------------------------------"
echo "PART 6: Automatic Path Creation"
echo "-----------------------------------------------------------------------------"
echo ""

# ---------------------------------------------------------------------------
# Create nested structure from empty object
# ---------------------------------------------------------------------------

echo "EXAMPLE 6.1: Create nested path from empty object"
echo "Command: echo '{}' | jn-edit .new.nested.path=value"
echo "Result:"
echo '{}' | $JN_EDIT .new.nested.path=value
echo ""
echo ""

# ---------------------------------------------------------------------------
# Build deeply nested config in one command
# ---------------------------------------------------------------------------

echo "EXAMPLE 6.2: Build deep structure from scratch"
echo "Command: echo '{}' | jn-edit .user.profile.settings.theme=dark"
echo "Result:"
echo '{}' | $JN_EDIT .user.profile.settings.theme=dark
echo ""
echo ""

# =============================================================================
# PART 7: REAL-WORLD PATTERNS
# =============================================================================

echo "-----------------------------------------------------------------------------"
echo "PART 7: Real-World Patterns"
echo "-----------------------------------------------------------------------------"
echo ""

# ---------------------------------------------------------------------------
# Pattern: In-place file editing (with backup)
# ---------------------------------------------------------------------------
# jn-edit is a filter, not an in-place editor. Use this pattern:

echo "PATTERN 7.1: In-place file editing"
echo ""
echo "  # Safe pattern with backup:"
echo "  jn-edit .version=2.0 < config.json > config.json.new && mv config.json.new config.json"
echo ""
echo "  # With sponge (from moreutils):"
echo "  cat config.json | jn-edit .version=2.0 | sponge config.json"
echo ""
echo ""

# ---------------------------------------------------------------------------
# Pattern: Conditional editing with jn filter
# ---------------------------------------------------------------------------
# Use jn filter to select records, then jn-edit to modify them

echo "PATTERN 7.2: Conditional editing"
echo ""
echo "  # Edit only admin users:"
echo "  cat users.ndjson | jn filter 'select(.role == \"admin\")' | jn-edit .privileged:=true"
echo ""
echo ""

# ---------------------------------------------------------------------------
# Pattern: Pipeline composition
# ---------------------------------------------------------------------------

echo "PATTERN 7.3: Pipeline composition"
echo ""
echo "  # Read CSV, add timestamp, write JSON:"
echo "  jn cat data.csv | jn-edit .imported_at=\"\$(date -Iseconds)\" | jn put output.json"
echo ""
echo "  # Fetch API, transform, store:"
echo "  jn cat 'https://api.example.com/users~json' | jn-edit .source=api | jn put users.ndjson"
echo ""
echo ""

# =============================================================================
echo "=============================================================================
Demo Complete

Key Takeaways:
- Use .path=value for strings, .path:=value for JSON types
- Use --del for explicit deletion (not null)
- Use --merge for bulk nested updates
- Use --append/--prepend for array operations
- jn-edit works on NDJSON streams for batch processing
============================================================================="
