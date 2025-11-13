# Shell Commands - Design Document

## Overview

Shell command plugins wrap Unix utilities and convert their output to NDJSON, enabling composable data pipelines from system commands. Each plugin parses the command's text output and emits structured JSON records.

**Philosophy:** Incorporate, don't replace. Wrap standard Unix utilities with simple Python parsers that generate JSON using schemas inspired by the [jc (JSON Convert)](https://github.com/kellyjonbrazil/jc) project.

## Architecture

### Core Pattern: Command → Parse in Python → NDJSON

Each shell plugin follows this simple pipeline:

```
Unix Command → Parse output line-by-line → NDJSON output
```

1. **Execute the command** as a subprocess (using `shlex` for safe parsing)
2. **Stream output line-by-line** (no buffering)
3. **Parse each line** with Python regex or string operations
4. **Emit JSON** following jc-inspired schemas
5. **Stream to stdout** for pipeline composition

### Why Not Use jc Directly?

We use **jc for inspiration** (JSON schemas, field names) but write our own parsers because:
- **Simplicity** - No external dependencies, just stdlib Python
- **Control** - We own the parsing logic and can optimize for streaming
- **Lightweight** - Each plugin is self-contained (~100 lines)
- **Backpressure** - Direct subprocess → parse → emit maintains streaming

### Command Invocation Syntax

Shell commands use two invocation styles:

#### 1. Via `jn cat` (Quoted)
```bash
jn cat "ls -l /tmp"
jn cat "find . -name '*.py'"
jn cat "ps aux"
```

Arguments must be quoted because the shell would otherwise parse them.

#### 2. Via `jn sh` (Greedy Args)
```bash
jn sh ls -l /tmp
jn sh find . -name "*.py"
jn sh ps aux
```

The `sh` command greedily consumes all arguments, so no quoting is needed.

## Plugin Structure

### Standard Shell Plugin Template

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []  # No dependencies needed!
# [tool.jn]
# matches = ["^ls($| )", "^ls .*"]
# ///

"""
JN Shell Plugin: ls

Execute `ls` command and convert output to NDJSON.

Usage:
    jn cat ls
    jn cat "ls -l"
    jn sh ls -la /tmp

Output schema: (inspired by jc --ls)
    {
        "filename": string,
        "flags": string,
        "owner": string,
        "size": integer,
        ...
    }
"""

import subprocess
import sys
import json
import shlex
import re


def parse_ls_long_line(line):
    """Parse a single line from ls -l output."""
    # Pattern: flags links owner group size date filename
    pattern = r'^([^\s]+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\w+\s+\d+\s+[\d:]+)\s+(.+)$'
    match = re.match(pattern, line)

    if not match:
        return None

    flags, links, owner, group, size, date, filename = match.groups()

    return {
        "filename": filename,
        "flags": flags,
        "links": int(links),
        "owner": owner,
        "group": group,
        "size": int(size),
        "date": date
    }


def reads(command_str=None):
    """Execute ls command and stream NDJSON records."""
    if not command_str:
        command_str = "ls"

    # Parse command string safely
    args = shlex.split(command_str)

    # Validate command
    if args[0] != 'ls':
        error = {"_error": f"Expected ls command, got: {args[0]}"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    # Detect if using long format
    has_long_flag = any('-l' in arg for arg in args[1:])

    # Execute command
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        bufsize=1  # Line buffered
    )

    # Stream output line-by-line
    for line in proc.stdout:
        line = line.rstrip()

        # Skip empty lines and "total" line
        if not line or line.startswith('total '):
            continue

        if has_long_flag:
            # Parse long format
            record = parse_ls_long_line(line)
            if record:
                print(json.dumps(record))
        else:
            # Simple format - just filename
            print(json.dumps({"filename": line}))

        sys.stdout.flush()

    proc.wait()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', default='read')
    parser.add_argument('address', nargs='?', help='Command string')
    args = parser.parse_args()

    if args.mode == 'read':
        reads(args.address)
```

### Key Implementation Details

#### 1. No Dependencies
```python
# /// script
# requires-python = ">=3.11"
# dependencies = []  # Just stdlib!
# ///
```

All plugins use only Python standard library.

#### 2. Regex Pattern Matching
```python
# [tool.jn]
# matches = ["^ls($| )", "^ls .*"]
```

- `^ls($| )` - Matches "ls" alone or "ls " followed by anything
- `^ls .*` - Matches "ls " followed by any arguments
- Pattern resolves to this specific plugin when user types `jn cat ls` or `jn sh ls`

#### 3. shlex for Safe Parsing
```python
args = shlex.split(command_str)  # "find . -name '*.py'" → ['find', '.', '-name', '*.py']
```

Never use `shell=True` in subprocess calls - it's a security risk.

#### 4. Line-by-Line Streaming
```python
for line in proc.stdout:
    line = line.rstrip()
    record = parse_line(line)
    print(json.dumps(record))
    sys.stdout.flush()
```

Process and emit each line immediately - no accumulation in memory.

#### 5. Error Handling

```python
except BrokenPipeError:
    # Expected when downstream closes (e.g., head)
    pass
except KeyboardInterrupt:
    # User pressed Ctrl+C
    pass
```

Both are normal termination conditions, not errors.

## Plugin Location

Shell command plugins are located in:
```
jn_home/plugins/shell/
```

This directory structure separates shell commands from:
- `formats/` - File format plugins (CSV, JSON, YAML)
- `protocols/` - Protocol plugins (HTTP, SMTP, Gmail)
- `filters/` - Filter plugins (jq)

## Current Shell Plugins

| Plugin | Command | Parser | Fields | Description |
|--------|---------|--------|--------|-------------|
| `ls_shell.py` | `ls` | regex | 7 | Directory listings (filename, flags, owner, size, etc.) |
| `ps_shell.py` | `ps` | split | 11 | Process info (pid, cpu%, mem%, command) |
| `env_shell.py` | `env` | split | 2 | Environment variables (name, value) |
| `find_shell.py` | `find` | simple | 1 | File search (path) |
| `tail_shell.py` | `tail` | simple | 2 | File tail/follow (line, line_number) |

## JSON Schemas (Inspired by jc)

### ls (Long Format)
```json
{
  "filename": "file.txt",
  "flags": "-rw-r--r--",
  "links": 1,
  "owner": "root",
  "group": "root",
  "size": 1234,
  "date": "Nov 13 10:21",
  "link_to": "target"  // Optional, for symlinks
}
```

### ps aux
```json
{
  "user": "root",
  "pid": 1,
  "cpu_percent": 0.0,
  "mem_percent": 0.1,
  "vsz": 169104,
  "rss": 13640,
  "tty": null,
  "stat": "Ss",
  "start": "Nov07",
  "time": "0:11",
  "command": "/sbin/init"
}
```

### env
```json
{
  "name": "PATH",
  "value": "/usr/local/bin:/usr/bin:/bin"
}
```

### find
```json
{
  "path": "/tmp/file.txt"
}
```

### tail
```json
{
  "line": "Log message here",
  "line_number": 42
}
```

## Next Shell Commands to Implement

Based on the jc project and common Unix usage patterns, these are the next priority shell commands:

### 1. du - Disk Usage
**Use case:** Find large directories consuming disk space

**Output schema:**
```json
{
  "size": integer,      // Size in blocks
  "path": string        // Directory/file path
}
```

**Parser:** Simple split on whitespace (2 columns)

**Example:**
```bash
jn sh du -h /var/log | jn filter '.size > 1000000'
```

### 2. df - Disk Free
**Use case:** Monitor filesystem usage

**Output schema:**
```json
{
  "filesystem": string,
  "size": integer,
  "used": integer,
  "available": integer,
  "use_percent": integer,
  "mounted_on": string
}
```

**Parser:** Split header, parse percentage

**Example:**
```bash
jn sh df -h | jn filter '.use_percent > 80'
```

### 3. who - Logged In Users
**Use case:** Security monitoring, see who's logged in

**Output schema:**
```json
{
  "user": string,
  "tty": string,
  "login_time": string,
  "from": string
}
```

**Parser:** Simple split on whitespace

**Example:**
```bash
jn sh who | jn filter '.user == "root"'
```

### 4. uptime - System Uptime
**Use case:** Monitor system load and uptime

**Output schema:**
```json
{
  "time": string,
  "uptime": string,
  "users": integer,
  "load_1m": float,
  "load_5m": float,
  "load_15m": float
}
```

**Parser:** Regex for single-line format

**Example:**
```bash
jn sh uptime | jn filter '.load_1m > 2.0'
```

### 5. netstat - Network Connections
**Use case:** Troubleshoot network issues, monitor connections

**Output schema:**
```json
{
  "proto": string,
  "local_address": string,
  "foreign_address": string,
  "state": string
}
```

**Parser:** Split on whitespace, handle varying column counts

**Example:**
```bash
jn sh netstat -tulpn | jn filter '.state == "LISTEN"'
```

## Performance Characteristics

### Memory Usage
**Constant ~1MB** regardless of data size, thanks to:
- OS pipe buffers (~64KB per pipe)
- Line-by-line processing
- No in-memory accumulation

### Streaming Behavior
```bash
jn sh find /huge/directory -name "*.log" | head -n 5
```

- Find starts outputting paths immediately
- Head terminates after 5 lines
- SIGPIPE propagates back to find
- Find terminates early (doesn't scan entire directory)
- Total data processed: ~5 files, not millions

### Parallel Execution
```bash
jn sh ls -l /usr/bin | jn filter '.size > 10000' | jn put large_files.json
```

Pipeline stages run concurrently:
```
CPU1: ███ ls
CPU2:    ███ parse
CPU3:       ███ filter
CPU4:          ███ write
```

## Implementation Guidelines

### When Creating New Shell Plugins

1. **Check jc schema first:**
   - Browse: https://github.com/kellyjonbrazil/jc/tree/master/jc/parsers
   - Look at docstring for schema definition
   - Use same field names and types

2. **Test command locally:**
   ```bash
   command args | head -10  # See the output format
   ```

3. **Copy an existing shell plugin as template:**
   - `ls_shell.py` - Complex regex parsing
   - `ps_shell.py` - Split-based parsing
   - `env_shell.py` - Simple key=value parsing
   - `find_shell.py` - Minimal wrapping (just add path field)

4. **Update these sections:**
   - `matches` regex pattern
   - Command validation (`args[0] != 'command'`)
   - Parser function (regex or split)
   - Documentation and schema

5. **Test with backpressure:**
   ```bash
   jn sh command args | head -n 5  # Should terminate early
   ```

## Parser Patterns

### Regex Parsing (ls)
For complex, fixed-format output:
```python
pattern = r'^([^\s]+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\w+\s+\d+\s+[\d:]+)\s+(.+)$'
match = re.match(pattern, line)
if match:
    flags, links, owner, group, size, date, filename = match.groups()
```

### Split Parsing (ps, env)
For whitespace-delimited columns:
```python
parts = line.split(None, 10)  # Split on any whitespace, max 11 parts
record = {
    "user": parts[0],
    "pid": int(parts[1]),
    ...
}
```

### Simple Wrapping (find, tail)
When output is already structured:
```python
record = {"path": line}  # Just wrap the line
```

## Security Considerations

### Never Use shell=True
```python
# WRONG - Shell injection vulnerability
subprocess.Popen(command_str, shell=True)

# CORRECT - Args list, no shell
args = shlex.split(command_str)
subprocess.Popen(args)
```

### Validate Command Name
```python
if args[0] != 'expected_command':
    error = {"_error": f"Expected {expected}, got: {args[0]}"}
    sys.exit(1)
```

This prevents users from running arbitrary commands through a plugin.

## Testing Shell Plugins

### Unit Testing
```python
# Test plugin directly
result = subprocess.run(
    [sys.executable, 'jn_home/plugins/shell/ls_shell.py', '--mode', 'read', 'ls'],
    capture_output=True, text=True
)
records = [json.loads(line) for line in result.stdout.strip().split('\n')]
assert len(records) > 0
assert 'filename' in records[0]
```

### Integration Testing via CLI
```bash
# Test through jn command
jn cat ls > /tmp/output.json
jn sh ps aux | head -n 5

# Test backpressure
jn sh find /large/dir -name "*.py" | head -n 10  # Should terminate early
```

### Performance Testing
```bash
# Memory should stay constant
/usr/bin/time -v jn sh find / -name "*.log" | head -n 100
# Check "Maximum resident set size" - should be ~5-10MB

# Streaming should be immediate
jn sh tail -f /var/log/syslog  # First line appears instantly
```

## References

- **jc Project (for schemas):** https://github.com/kellyjonbrazil/jc
- **jc Parsers (for field names):** https://github.com/kellyjonbrazil/jc/tree/master/jc/parsers
- **JN Architecture:** `spec/arch/design.md`
- **Backpressure Design:** `spec/arch/backpressure.md`
