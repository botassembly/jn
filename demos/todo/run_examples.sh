#!/usr/bin/env bash
# =============================================================================
# JN Todo Tool Demo
# =============================================================================
#
# This demo showcases the todo CLI tool, which demonstrates how JN utility
# tools leverage NDJSON storage with jn-edit and zq for mutations and queries.
#
# The todo tool is located at: jn_home/tools/todo
# Access it via: jn tool todo <command>
#
# For convenience, create an alias:
#   alias todo="jn tool todo"
#
# NOTE: IDs are XIDs (20-char, time-sortable). You can use partial prefixes
# like the first 5-8 characters to reference todos.
#
# =============================================================================

set -euo pipefail

# Use jn tool to access the todo command
# In practice, you'd create an alias: alias todo="jn tool todo"
JN="${JN:-jn}"
TODO="$JN tool todo"
ZQ="${ZQ:-zq}"

# Colors for demo output
CYAN='\033[0;36m'
GREEN='\033[0;32m'
RESET='\033[0m'

demo() {
    echo -e "\n${CYAN}▶ $1${RESET}"
    echo "$ $2"
    eval "$2"
}

# Helper to get the ID of the Nth todo (1-indexed)
get_id() {
    local n=$1
    $ZQ -r '.id' < .todo.jsonl 2>/dev/null | sed -n "${n}p"
}

# Helper to get short ID (first 8 chars)
short_id() {
    echo "${1:0:8}"
}

echo "=============================================="
echo "         JN Todo Tool Demo"
echo "=============================================="
echo ""
echo "This demo shows the todo CLI built on JN's"
echo "NDJSON infrastructure using jn-edit and zq."
echo ""
echo "IDs are XIDs - time-sortable unique identifiers."
echo "Use partial prefixes (first 5-8 chars) to reference."
echo ""

# -----------------------------------------------------------------------------
# BASIC OPERATIONS
# -----------------------------------------------------------------------------
demo "Create a fresh todo list" "rm -f .todo.jsonl .todo.jsonl.bak"

demo "Add a simple task" "$TODO add 'Buy groceries'"

demo "Add task with priority" "$TODO add 'Fix critical bug' -p high"

demo "Add task with due date" "$TODO add 'Submit report' -d 2024-12-20"

demo "Add task with tags" "$TODO add 'Review PR for auth feature' -t '@work,@review'"

demo "List all todos" "$TODO list"

# Capture IDs for later use
ID1=$(get_id 1)  # Buy groceries
ID2=$(get_id 2)  # Fix critical bug
ID3=$(get_id 3)  # Submit report
ID4=$(get_id 4)  # Review PR

echo -e "\n${GREEN}Captured IDs for reference:${RESET}"
echo "  Task 1 (Buy groceries): $(short_id $ID1)"
echo "  Task 2 (Fix bug):       $(short_id $ID2)"
echo "  Task 3 (Submit report): $(short_id $ID3)"
echo "  Task 4 (Review PR):     $(short_id $ID4)"

# -----------------------------------------------------------------------------
# FILTERING
# -----------------------------------------------------------------------------
demo "Filter by priority" "$TODO list high"

demo "Filter by tag" "$TODO list @work"

demo "Search by text" "$TODO search 'bug'"

# -----------------------------------------------------------------------------
# COMPLETING TASKS
# -----------------------------------------------------------------------------
demo "Mark task as done (using partial ID)" "$TODO done $(short_id $ID1)"

demo "List shows completed task" "$TODO list"

demo "Skip a task" "$TODO skip $(short_id $ID3)"

demo "List pending only" "$TODO list pending"

# -----------------------------------------------------------------------------
# DEPENDENCIES (BEADS-INSPIRED)
# -----------------------------------------------------------------------------
demo "Add tasks for dependency demo" "
$TODO add 'Write tests'
$TODO add 'Code review'
$TODO add 'Deploy to staging'
"

# Capture new IDs
ID5=$(get_id 5)  # Write tests
ID6=$(get_id 6)  # Code review
ID7=$(get_id 7)  # Deploy to staging

echo -e "\n${GREEN}New task IDs:${RESET}"
echo "  Task 5 (Write tests):  $(short_id $ID5)"
echo "  Task 6 (Code review):  $(short_id $ID6)"
echo "  Task 7 (Deploy):       $(short_id $ID7)"

demo "Set up blocker chain: tests → review → deploy" "
$TODO blocks $(short_id $ID5) $(short_id $ID6)
$TODO blocks $(short_id $ID6) $(short_id $ID7)
"

demo "Show ready tasks (no blockers)" "$TODO ready"

demo "Show blocked tasks" "$TODO blocked"

demo "Complete blocker to unblock next" "$TODO done $(short_id $ID5)"

demo "Now task 6 (Code review) is ready" "$TODO ready"

demo "View dependency tree" "$TODO tree $(short_id $ID7)"

# -----------------------------------------------------------------------------
# SUBTASKS
# -----------------------------------------------------------------------------
demo "Add main task and subtasks" "
$TODO add 'Main project task'
"

ID8=$(get_id 8)  # Main project task
echo -e "${GREEN}Main task ID: $(short_id $ID8)${RESET}"

demo "Add subtasks (using partial parent ID)" "
$TODO add 'Research options' --parent $(short_id $ID8)
$TODO add 'Write implementation' --parent $(short_id $ID8)
$TODO add 'Write documentation' --parent $(short_id $ID8)
"

demo "List shows subtasks indented" "$TODO list"

# -----------------------------------------------------------------------------
# NOTES
# -----------------------------------------------------------------------------
demo "Add notes to a task" "$TODO note $(short_id $ID2) 'Check error handling edge cases'"

demo "View task notes" "$TODO note $(short_id $ID2)"

# -----------------------------------------------------------------------------
# WORKFLOW COMMANDS
# -----------------------------------------------------------------------------
demo "Bump priority (cycles low→med→high→low)" "$TODO bump $(short_id $ID6)"

demo "Reopen a completed task" "$TODO reopen $(short_id $ID1)"

demo "Bulk rename tags" "$TODO retag '@work' '@office'"

# -----------------------------------------------------------------------------
# ANALYTICS
# -----------------------------------------------------------------------------
demo "View statistics dashboard" "$TODO stats"

demo "Quick count" "$TODO count"

# -----------------------------------------------------------------------------
# EXPORT
# -----------------------------------------------------------------------------
demo "Export to markdown" "$TODO export"

# -----------------------------------------------------------------------------
# UNDO
# -----------------------------------------------------------------------------
demo "Undo last change (restores from backup)" "$TODO undo"

# -----------------------------------------------------------------------------
# XID TIME FEATURES
# -----------------------------------------------------------------------------
echo -e "\n${GREEN}━━━ XID TIME FEATURES ━━━${RESET}"
echo ""
echo "XIDs embed creation timestamps. Use ZQ to extract:"

demo "View raw todo data with IDs" "head -2 .todo.jsonl"

demo "Extract creation time from XID" "echo '{\"id\":\"$ID1\"}' | $ZQ -r '.id | xid_time | ago'"

echo ""
echo "=============================================="
echo "         Demo Complete!"
echo "=============================================="
echo ""
echo "The todo tool stores data in .todo.jsonl"
echo "Each record is a JSON object with fields:"
echo "  id (XID), text, status, priority, due,"
echo "  tags, notes, blockers, parent"
echo ""
echo "XIDs are time-sortable - creation time is embedded."
echo "Use ZQ's xid_time() to extract the timestamp."
echo ""
echo "View raw data: cat .todo.jsonl | jq ."
echo ""
echo "Create an alias for daily use:"
echo "  alias todo=\"jn tool todo\""
echo ""
