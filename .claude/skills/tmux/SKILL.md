---
name: tmux
description: Remote control tmux sessions for interactive CLI tools (python REPL, debuggers, database shells, long-running servers). Send keystrokes and capture output programmatically. Use when debugging, running interactive shells, or monitoring long-running processes.
allowed-tools: Bash, Read
---

# tmux Interactive CLI Control

Control interactive command-line tools programmatically using tmux as a terminal multiplexer. Works on Linux and macOS with stock tmux.

## Core Concept

Use tmux with a private socket to create isolated sessions that can be controlled via send-keys and monitored via capture-pane. This enables programmatic interaction with tools that require TTY (Python REPL, debuggers, database shells, etc.).

## Critical Setup Pattern

```bash
# Standard socket location for all agent sessions
SOCKET_DIR=${TMPDIR:-/tmp}/claude-tmux-sockets
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/claude.sock"

# Create session with descriptive name
SESSION=claude-python
tmux -S "$SOCKET" new -d -s "$SESSION" -n shell

# Start interactive tool
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'python3 -q' Enter

# Capture output
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -200

# Clean up when done
tmux -S "$SOCKET" kill-session -t "$SESSION"
```

## Always Tell the User How to Monitor

**CRITICAL:** After starting ANY tmux session, immediately print monitoring instructions:

```bash
# Right after session creation, print this:
echo "To monitor this session yourself:"
echo "  tmux -S \"$SOCKET\" attach -t $SESSION"
echo ""
echo "Or to capture output once:"
echo "  tmux -S \"$SOCKET\" capture-pane -p -J -t $SESSION:0.0 -S -200"
```

**Repeat these instructions at the end of your work** so the user knows how to continue monitoring.

## Socket Convention

**Required Standards:**
- **Socket directory:** `CLAUDE_TMUX_SOCKET_DIR` (defaults to `${TMPDIR:-/tmp}/claude-tmux-sockets`)
- **Always create dir first:** `mkdir -p "$CLAUDE_TMUX_SOCKET_DIR"`
- **Default socket:** `SOCKET="$CLAUDE_TMUX_SOCKET_DIR/claude.sock"`
- **Use `-S "$SOCKET"`** consistently to stay on the private socket
- **Session names:** Short, slug-like (e.g., `claude-py`, `claude-gdb`, `claude-server`)
- **Target format:** `{session}:{window}.{pane}` (defaults to `:0.0` if omitted)

**Clean config:** Add `-f /dev/null` to ignore user's tmux.conf:
```bash
tmux -S "$SOCKET" -f /dev/null new -d -s "$SESSION"
```

## Finding Sessions

**List sessions on current socket:**
```bash
tmux -S "$SOCKET" list-sessions
tmux -S "$SOCKET" list-panes -a
```

**List sessions with metadata:**
```bash
tmux -S "$SOCKET" list-sessions -F '#{session_name} created:#{session_created} windows:#{session_windows}'
```

**Check if session exists:**
```bash
if tmux -S "$SOCKET" has-session -t "$SESSION" 2>/dev/null; then
    echo "Session exists"
fi
```

## Sending Commands

**Literal text (preferred - avoids shell expansion):**
```bash
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -l -- "$command"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- Enter
```

**With Enter in one call:**
```bash
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'python3 -q' Enter
```

**Control characters:**
```bash
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 C-c     # Interrupt
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 C-d     # EOF
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 C-z     # Suspend
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 Escape  # Escape
```

**Multi-line with proper quoting:**
```bash
# Single quotes prevent expansion
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'for i in range(10): print(i)' Enter
```

## Watching Output

**Capture recent history (joined lines):**
```bash
# -p: print to stdout
# -J: join wrapped lines
# -S -200: start from 200 lines back
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -200
```

**Capture everything:**
```bash
# -S -: start from beginning of scrollback buffer
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -
```

**Attach to watch interactively:**
```bash
tmux -S "$SOCKET" attach -t "$SESSION"
# Detach with Ctrl+b d
```

**Poll for specific output (wait pattern):**
```bash
# Wait up to 15 seconds for pattern to appear
timeout=15
interval=0.5
elapsed=0

while [ $elapsed -lt $timeout ]; do
    output=$(tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -200)
    if echo "$output" | grep -q "expected_pattern"; then
        echo "Pattern found!"
        break
    fi
    sleep $interval
    elapsed=$((elapsed + 1))
done
```

## Common Interactive Tools

### Python REPL

**CRITICAL:** Always set `PYTHON_BASIC_REPL=1` to avoid interference:

```bash
SESSION=claude-python
tmux -S "$SOCKET" new -d -s "$SESSION"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'PYTHON_BASIC_REPL=1 python3 -q' Enter

# Wait for prompt
sleep 1

# Send code (use -l for literal to avoid shell issues)
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -l -- 'import sys'
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- Enter

tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -l -- 'print(sys.version)'
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- Enter

# Capture output
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -50

# Exit
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'exit()' Enter
```

### GDB / LLDB Debugger

**Use lldb by default:**

```bash
SESSION=claude-lldb
tmux -S "$SOCKET" new -d -s "$SESSION"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'lldb ./program' Enter

# Wait for prompt
sleep 1

# Disable paging
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'settings set auto-confirm true' Enter

# Set breakpoint
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'b main' Enter

# Run
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'run' Enter

# Capture output
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -100

# Continue execution
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'continue' Enter

# Exit
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'quit' Enter
```

**For GDB:**
```bash
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'gdb --quiet ./program' Enter
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'set pagination off' Enter
```

### Database Shells (psql, mysql, sqlite3)

```bash
SESSION=claude-db
tmux -S "$SOCKET" new -d -s "$SESSION"

# PostgreSQL
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'psql -d mydb' Enter
sleep 1
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'SELECT * FROM users LIMIT 5;' Enter

# MySQL
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'mysql -u root mydb' Enter
sleep 1
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'SELECT * FROM users LIMIT 5;' Enter

# SQLite
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'sqlite3 mydb.db' Enter
sleep 1
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- '.tables' Enter
```

### Long-Running Servers

```bash
SESSION=claude-server
tmux -S "$SOCKET" new -d -s "$SESSION"

# HTTP server
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'python3 -m http.server 8000' Enter

# Tell user how to monitor
echo "Server started in tmux session. Monitor with:"
echo "  tmux -S \"$SOCKET\" attach -t $SESSION"

# Check if server started
sleep 2
output=$(tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -20)
echo "$output" | grep -q "Serving HTTP" && echo "Server running!"

# To stop later:
# tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 C-c
```

### Node REPL

```bash
SESSION=claude-node
tmux -S "$SOCKET" new -d -s "$SESSION"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'node' Enter
sleep 1

# Send JavaScript
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -l -- 'const x = [1,2,3,4,5]'
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- Enter

tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -l -- 'x.map(n => n * 2)'
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- Enter

# Capture
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -30
```

## Cleanup

**Kill specific session:**
```bash
tmux -S "$SOCKET" kill-session -t "$SESSION"
```

**Kill all sessions on socket:**
```bash
tmux -S "$SOCKET" list-sessions -F '#{session_name}' | \
    xargs -I {} tmux -S "$SOCKET" kill-session -t {}
```

**Kill entire server (all sessions):**
```bash
tmux -S "$SOCKET" kill-server
```

**Clean up socket directory:**
```bash
rm -rf "$CLAUDE_TMUX_SOCKET_DIR"
```

## Polling Pattern for Output

When you need to wait for specific output before proceeding:

```bash
wait_for_output() {
    local target=$1
    local pattern=$2
    local timeout=${3:-15}
    local interval=${4:-0.5}
    local history_lines=${5:-1000}

    local elapsed=0

    while [ $(echo "$elapsed < $timeout" | bc) -eq 1 ]; do
        output=$(tmux -S "$SOCKET" capture-pane -p -J -t "$target" -S -"$history_lines")

        if echo "$output" | grep -q "$pattern"; then
            return 0
        fi

        sleep "$interval"
        elapsed=$(echo "$elapsed + $interval" | bc)
    done

    echo "Timeout waiting for pattern: $pattern" >&2
    echo "Last output:" >&2
    echo "$output" >&2
    return 1
}

# Usage
wait_for_output "$SESSION:0.0" ">>>" 15 0.5 2000
```

## JN-Specific Use Cases

### Interactive JN Plugin Development

Test plugins interactively with immediate feedback:

```bash
SESSION=claude-jn-plugin
SOCKET_DIR=${TMPDIR:-/tmp}/claude-tmux-sockets
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/claude.sock"

# Start Python REPL for plugin development
tmux -S "$SOCKET" new -d -s "$SESSION"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'cd /Users/ian/botassembly/jn' Enter
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'PYTHON_BASIC_REPL=1 uv run python3 -q' Enter

sleep 1

# Test plugin interactively
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -l -- 'import sys, json'
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- Enter

tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -l -- 'sys.path.insert(0, "jn_home/plugins/formats")'
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- Enter

tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -l -- 'import csv_'
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- Enter

# Capture to see imports worked
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -50

echo "Monitor the session with:"
echo "  tmux -S \"$SOCKET\" attach -t $SESSION"
```

### Running JN Pipelines with Monitoring

For long-running JN pipelines:

```bash
SESSION=claude-jn-pipeline
tmux -S "$SOCKET" new -d -s "$SESSION"

# Run JN pipeline
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- \
    'jn cat large_data.csv | jn filter ".amount > 1000" | jn put filtered.json' Enter

echo "Pipeline running in tmux. Monitor progress with:"
echo "  tmux -S \"$SOCKET\" attach -t $SESSION"
echo ""
echo "Or check current output:"
echo "  tmux -S \"$SOCKET\" capture-pane -p -J -t $SESSION:0.0 -S -100"

# Poll for completion
sleep 5
output=$(tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -50)
if echo "$output" | grep -q "error\|Error\|ERROR"; then
    echo "Pipeline encountered errors:"
    echo "$output"
fi
```

### Debugging JN with pdb

```bash
SESSION=claude-jn-debug
tmux -S "$SOCKET" new -d -s "$SESSION"

# Start Python with debugger
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'cd /Users/ian/botassembly/jn' Enter
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'PYTHON_BASIC_REPL=1 uv run python3 -m pdb -c continue src/jn/cli/main.py cat data.csv' Enter

sleep 2

# Set breakpoint
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'b src/jn/plugins/discovery.py:45' Enter
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'continue' Enter

echo "Debugger running. Attach with:"
echo "  tmux -S \"$SOCKET\" attach -t $SESSION"
```

## Best Practices

1. **Always use isolated sockets** - Keep agent sessions separate from personal tmux
2. **Always print monitor commands** - Tell user how to watch after starting session
3. **Wait after starting tools** - Give interactive tools time to initialize (sleep 1-2 seconds)
4. **Use `-l` for literal sends** - Avoid shell expansion issues with complex commands
5. **Capture with `-J`** - Join wrapped lines to avoid artifacts
6. **Poll for completion** - Don't assume instant execution; wait for expected output
7. **Clean up sessions** - Kill sessions when done to avoid clutter
8. **Handle errors gracefully** - Check capture output for error patterns

## Troubleshooting

**Session not found:**
```bash
# List all sessions to verify
tmux -S "$SOCKET" list-sessions
```

**No output captured:**
```bash
# Increase history lines
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -5000
```

**Commands not executing:**
```bash
# Verify session is running
tmux -S "$SOCKET" list-panes -a -F '#{pane_pid} #{pane_current_command}'

# Check if process is responsive
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- Enter
sleep 1
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -10
```

**Python REPL interference:**
```bash
# ALWAYS set PYTHON_BASIC_REPL=1
PYTHON_BASIC_REPL=1 python3 -q
```

## Quick Reference

| Action | Command |
|--------|---------|
| Create session | `tmux -S "$SOCKET" new -d -s "$SESSION"` |
| Send text | `tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -l -- "text"` |
| Send Enter | `tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- Enter` |
| Send Ctrl-C | `tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 C-c` |
| Capture output | `tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -200` |
| Attach (watch) | `tmux -S "$SOCKET" attach -t "$SESSION"` |
| List sessions | `tmux -S "$SOCKET" list-sessions` |
| Kill session | `tmux -S "$SOCKET" kill-session -t "$SESSION"` |
| Kill all | `tmux -S "$SOCKET" kill-server` |
