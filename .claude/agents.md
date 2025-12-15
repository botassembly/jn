# JN - Agent Guide

This document helps AI agents work effectively with the JN codebase.

## Quick Setup

```bash
# Build and activate (required before using jn commands)
make build
source dist/activate.sh

# Verify setup
jn --version
echo '{"test":1}' | jn filter '.'
```

## Using the Todo Tool

JN includes a built-in task management tool accessible via `jn tool todo` (or just `todo` after sourcing activate.sh).

### Basic Usage

```bash
# Add tasks
todo add "Implement feature X"
todo add -p high "Fix critical bug"          # Priority: high/med/low
todo add -d 2024-12-25 "Holiday release"     # Due date
todo add --parent 1 "Subtask of #1"          # Subtasks

# View tasks
todo list                  # All todos
todo ready                 # Tasks with no blockers (actionable now)
todo blocked               # Tasks waiting on dependencies
todo stats                 # Dashboard with statistics

# Complete tasks
todo done 1                # Mark #1 as done
todo skip 2                # Skip #2
todo reopen 1              # Reopen completed task
```

### Dependency Management (BEADS-inspired)

```bash
# Task 1 must complete before task 2 can start
todo blocks 1 2

# Remove blocker
todo unblock 1 2

# Visualize dependencies
todo tree
todo tree 5               # Show tree for specific task
```

### Organization

```bash
# Tags (auto-extracted from @mentions and #hashtags)
todo add "Fix bug @alice #urgent"
todo list @alice          # Filter by tag
todo list #urgent

# Notes
todo note 1 "Added workaround for edge case"
todo note 1               # View notes

# Priority management
todo bump 1               # Cycle: low -> med -> high -> low

# Search
todo search "bug"
```

### Data Location

Todo data is stored in `.todo.jsonl` in the current working directory (NDJSON format).

## Development Workflow

### Building Single Tools

When modifying a single tool, rebuild only that component:

```bash
# Rebuild specific tool
make tool-jn-cat
cp tools/zig/jn-cat/bin/jn-cat dist/bin/

# Test immediately
echo 'a,b\n1,2' | jn cat -~csv
```

### Full Validation

```bash
make test      # Unit tests
make check     # Integration tests
make fmt       # Format code (required before commit)
```

## CLI Argument Notes

Short options require `=` syntax:
```bash
jn head --lines=5    # Works
jn head -n=5         # Works
jn head -n 5         # Does NOT work (space-separated)
```

## Key Commands

| Task | Command |
|------|---------|
| Read CSV | `jn cat data.csv` |
| Filter data | `jn filter '.age > 25'` |
| Write JSON | `jn put output.json` |
| Preview | `jn head -n 10` |
| Visual explore | `jn vd data.csv` |
| Task list | `todo list` |
| Actionable tasks | `todo ready` |

## Project Structure

```
jn/
├── tools/zig/         # CLI tools (jn, jn-cat, jn-put, jn-filter, etc.)
├── plugins/zig/       # Format plugins (csv, json, yaml, toml, gz)
├── zq/                # Filter engine
├── jn_home/
│   ├── tools/         # Utility tools (todo)
│   └── plugins/       # Python plugins (xlsx, gmail, mcp, duckdb)
├── spec/              # Architecture documentation (14 docs)
└── dist/              # Built distribution (after make build)
```

## Recent Updates

- **jn tool todo**: Full-featured task management with BEADS-inspired dependency tracking
  - Blockers and dependency trees
  - Priority levels (high/med/low)
  - Due dates and overdue tracking
  - Tags (@mentions, #hashtags)
  - Notes and subtasks
  - Statistics dashboard
- **jn-edit tool**: Surgical JSON editing for scripts and tools
- **Release workflow**: Version embedding and GitHub releases via git tags
