# Todo CLI Demo

Demonstrates JN tools architecture using a task management CLI.

## Quick Start

```bash
# From this directory
./todo add "My first task"
./todo list

# Or via jn tool (when installed)
jn tool todo add "My first task"

# Or create an alias
alias todo="jn tool todo"
todo list
```

## About

This demo shows how standalone tools can leverage JN's infrastructure:
- **Storage**: NDJSON file (`.todo.jsonl`)
- **Queries**: `zq` for filtering and aggregations
- **Mutations**: `jn-edit` for field updates

The tool is a single bash script with no dependencies beyond `jn-edit` and `zq`.

## Features

### Basic Operations
```bash
todo add "Buy milk"                    # Add task
todo add "Fix bug" -p high             # With priority
todo add "Review PR" -d 2024-01-15     # With due date
todo add "Deploy" -t "@work,@urgent"   # With tags
todo done 1                            # Complete task
todo skip 2                            # Skip task
todo rm 3                              # Delete task
```

### Filtering
```bash
todo list                   # All todos
todo list pending           # Only pending
todo list done              # Only completed
todo list --priority high   # By priority
todo list --tag "@work"     # By tag
todo search "bug"           # Full-text search
```

### BEADS-Inspired Features
```bash
# Dependency tracking
todo blocks 1 2             # Task 1 blocks task 2
todo unblock 1 2            # Remove blocker
todo ready                  # Show unblocked tasks
todo blocked                # Show blocked tasks
todo tree                   # Dependency visualization

# Subtasks
todo add "Write tests" --parent 1    # Creates 1.1
todo add "Write docs" --parent 1     # Creates 1.2

# Workflow
todo bump 1                 # Cycle priority (low→med→high)
todo reopen 1               # Restore completed task
todo retag "@old" "@new"    # Bulk rename tags
```

### Notes & Metadata
```bash
todo note 1 "Remember to check edge cases"
todo notes 1                # Show notes
```

### Utilities
```bash
todo stats                  # Dashboard
todo export                 # Markdown export
todo undo                   # Restore from backup
todo count                  # Quick count
```

## Data Format

Each todo is a JSON object:

```json
{
  "id": 1,
  "text": "Fix the login bug",
  "status": "pending",
  "priority": "high",
  "due": "2024-01-15",
  "tags": ["@work", "@urgent"],
  "notes": ["Check session handling"],
  "blockers": [2, 3],
  "parent": null,
  "created": "2024-01-10T10:30:00"
}
```

## Architecture

```
demos/todo-cli/
├── todo           # The CLI script (also at jn_home/tools/todo)
├── README.md      # This file
└── .todo.jsonl    # Local data (gitignored)
```

The canonical location is `jn_home/tools/todo`. This demo directory exists for development and documentation.

## See Also

- `jn_home/tools/README.md` - Full tools architecture and future ideas
- BEADS issue tracker - Inspiration for dependency features
