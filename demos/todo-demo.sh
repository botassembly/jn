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
# =============================================================================

set -euo pipefail

# Use jn tool to access the todo command
# In practice, you'd create an alias: alias todo="jn tool todo"
JN="${JN:-./tools/zig/jn/bin/jn}"
TODO="$JN tool todo"

# Colors for demo output
CYAN='\033[0;36m'
RESET='\033[0m'

demo() {
    echo -e "\n${CYAN}▶ $1${RESET}"
    echo "$ $2"
    eval "$2"
}

echo "=============================================="
echo "         JN Todo Tool Demo"
echo "=============================================="
echo ""
echo "This demo shows the todo CLI built on JN's"
echo "NDJSON infrastructure using jn-edit and zq."
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

# -----------------------------------------------------------------------------
# FILTERING
# -----------------------------------------------------------------------------
demo "Filter by priority" "$TODO list --priority high"

demo "Filter by tag" "$TODO list --tag '@work'"

demo "Search by text" "$TODO search 'bug'"

# -----------------------------------------------------------------------------
# COMPLETING TASKS
# -----------------------------------------------------------------------------
demo "Mark task as done" "$TODO done 1"

demo "List shows completed task" "$TODO list"

demo "Skip a task" "$TODO skip 3"

demo "List pending only" "$TODO list pending"

# -----------------------------------------------------------------------------
# DEPENDENCIES (BEADS-INSPIRED)
# -----------------------------------------------------------------------------
demo "Add tasks for dependency demo" "
$TODO add 'Write tests'
$TODO add 'Code review'
$TODO add 'Deploy to staging'
"

demo "Set up blocker chain: tests → review → deploy" "
$TODO blocks 5 6
$TODO blocks 6 7
"

demo "Show ready tasks (no blockers)" "$TODO ready"

demo "Show blocked tasks" "$TODO blocked"

demo "Complete blocker to unblock next" "$TODO done 5"

demo "Now task 6 is ready" "$TODO ready"

demo "View dependency tree" "$TODO tree 7"

# -----------------------------------------------------------------------------
# SUBTASKS
# -----------------------------------------------------------------------------
demo "Add subtasks" "
$TODO add 'Main project task'
$TODO add 'Research options' --parent 8
$TODO add 'Write implementation' --parent 8
$TODO add 'Write documentation' --parent 8
"

demo "List shows subtasks indented" "$TODO list"

# -----------------------------------------------------------------------------
# NOTES
# -----------------------------------------------------------------------------
demo "Add notes to a task" "$TODO note 2 'Check error handling edge cases'"

demo "View task notes" "$TODO notes 2"

# -----------------------------------------------------------------------------
# WORKFLOW COMMANDS
# -----------------------------------------------------------------------------
demo "Bump priority (cycles low→med→high→low)" "$TODO bump 6"

demo "Reopen a completed task" "$TODO reopen 1"

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

echo ""
echo "=============================================="
echo "         Demo Complete!"
echo "=============================================="
echo ""
echo "The todo tool stores data in .todo.jsonl"
echo "Each record is a JSON object with fields:"
echo "  id, text, status, priority, due, tags,"
echo "  notes, blockers, parent, created"
echo ""
echo "View raw data: cat .todo.jsonl | jq ."
echo ""
echo "Create an alias for daily use:"
echo "  alias todo=\"jn tool todo\""
echo ""
