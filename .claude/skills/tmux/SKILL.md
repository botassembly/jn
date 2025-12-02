---
name: tmux
description: Use tmux to programmatically control interactive CLI tools like VisiData, PDB, database shells, and REPLs. Send keystrokes and capture output without requiring user interaction.
allowed-tools: Bash, Read
---

# tmux - Control Interactive CLI Tools

Use tmux to run and control interactive programs (VisiData, PDB, mysql, psql, etc.) programmatically.

## The Pattern

**Every interactive tool uses the same 3-step pattern:**

### Step 1: Create Session

```bash
SOCKET="/tmp/claude-tmux-sockets/claude.sock"
SESSION="my-session"

mkdir -p /tmp/claude-tmux-sockets
tmux -S "$SOCKET" new -d -s "$SESSION" "your_command_here"
sleep 1
```

### Step 2: Discover Pane (Always :1.1)

```bash
# Check what the pane target is (always :1.1 in our setup)
tmux -S "$SOCKET" list-panes -a -F '#{session_name}:#{window_index}.#{pane_index}'
# Output: my-session:1.1

# Use this pane target for all commands
PANE="my-session:1.1"
```

### Step 3: Send Commands & Capture

```bash
# Send keystrokes
tmux -S "$SOCKET" send-keys -t "$PANE" "your_command" Enter
sleep 1

# Capture output
tmux -S "$SOCKET" capture-pane -p -J -t "$PANE" -S -20

# Cleanup when done
tmux -S "$SOCKET" kill-session -t "$SESSION"
```

## Complete Examples

### VisiData

```bash
SOCKET="/tmp/claude-tmux-sockets/claude.sock"
SESSION="vd-session"
PANE="vd-session:1.1"

mkdir -p /tmp/claude-tmux-sockets
tmux -S "$SOCKET" new -d -s "$SESSION" "vd data.csv"
sleep 2

# Navigate to bottom
tmux -S "$SOCKET" send-keys -t "$PANE" "G"
sleep 1

# Capture view
tmux -S "$SOCKET" capture-pane -p -J -t "$PANE" -S -20

# Quit
tmux -S "$SOCKET" send-keys -t "$PANE" "gq"
tmux -S "$SOCKET" kill-session -t "$SESSION"
```

### PDB (Python Debugger)

```bash
SOCKET="/tmp/claude-tmux-sockets/claude.sock"
SESSION="pdb-session"
PANE="pdb-session:1.1"

mkdir -p /tmp/claude-tmux-sockets
tmux -S "$SOCKET" new -d -s "$SESSION"
sleep 1

# Start PDB
tmux -S "$SOCKET" send-keys -t "$PANE" "python -m pdb script.py" Enter
sleep 1

# Set breakpoint
tmux -S "$SOCKET" send-keys -t "$PANE" "break 10" Enter
tmux -S "$SOCKET" send-keys -t "$PANE" "continue" Enter
sleep 1

# Inspect variables
tmux -S "$SOCKET" send-keys -t "$PANE" "p my_variable" Enter
sleep 0.5

# Capture
tmux -S "$SOCKET" capture-pane -p -J -t "$PANE" -S -20

# Quit
tmux -S "$SOCKET" send-keys -t "$PANE" "quit" Enter
tmux -S "$SOCKET" kill-session -t "$SESSION"
```

### Database Shell (psql, mysql, sqlite3)

```bash
SOCKET="/tmp/claude-tmux-sockets/claude.sock"
SESSION="db-session"
PANE="db-session:1.1"

mkdir -p /tmp/claude-tmux-sockets
tmux -S "$SOCKET" new -d -s "$SESSION"
sleep 1

# Start database
tmux -S "$SOCKET" send-keys -t "$PANE" "sqlite3 mydb.db" Enter
sleep 1

# Run query
tmux -S "$SOCKET" send-keys -t "$PANE" "SELECT * FROM users LIMIT 5;" Enter
sleep 0.5

# Capture results
tmux -S "$SOCKET" capture-pane -p -J -t "$PANE" -S -20

# Exit
tmux -S "$SOCKET" send-keys -t "$PANE" ".quit" Enter
tmux -S "$SOCKET" kill-session -t "$SESSION"
```

## Critical Rules

### 1. Pane is Always :1.1

In our setup, the pane target is **always** `session-name:1.1`, not `:0.0`.

**Don't guess - verify once:**
```bash
tmux -S "$SOCKET" list-panes -a
# Shows: session-name:1.1: [80x24] ...
```

### 2. Never Use Command Substitution

**❌ WRONG - Causes parse error:**
```bash
PANE=$(tmux list-panes ...)  # parse error near '('
```

**✅ CORRECT - Hardcode the pane:**
```bash
PANE="my-session:1.1"  # Always :1.1 in our setup
```

### 3. Tell User How to Monitor

Always print this after creating a session:
```bash
echo "Monitor with: tmux -S \"$SOCKET\" attach -t $SESSION"
echo "Detach with: Ctrl+b d"
```

### 4. Wait After Commands

Interactive programs need time to process:
```bash
tmux send-keys -t "$PANE" "command" Enter
sleep 1  # Give it time to execute
tmux capture-pane -p -J -t "$PANE" -S -20
```

## User Monitoring

Users can attach to watch:
```bash
# In their terminal
tmux -S "/tmp/claude-tmux-sockets/claude.sock" attach -t session-name

# Detach without quitting: Ctrl+b d
```

## Cleanup

```bash
# Kill specific session
tmux -S "$SOCKET" kill-session -t "$SESSION"

# Kill all sessions
tmux -S "$SOCKET" kill-server
```

## That's It

Three steps for any interactive tool:
1. Create session with tool running
2. Use pane `:1.1`
3. Send keys, capture output

Works the same for VisiData, PDB, psql, mysql, Python REPL, node, etc.
