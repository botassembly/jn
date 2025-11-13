# Shell Commands - Design Document

## Overview

Shell command plugins wrap Unix utilities and convert their output to NDJSON, enabling composable data pipelines from system commands. This approach follows the Unix philosophy: use existing battle-tested tools and compose them together.

**Philosophy:** Incorporate, don't replace. Wrap standard Unix utilities with thin Python adapters that handle streaming and backpressure correctly.

## Architecture

### Core Pattern: Command → JC → NDJSON

Each shell plugin follows this pipeline:

```
Unix Command → jc parser → NDJSON output
```

1. **Execute the command** as a subprocess (using `shlex` for safe parsing)
2. **Pipe output to jc** for JSON conversion
3. **Convert to NDJSON** (one JSON object per line)
4. **Stream to stdout** for pipeline composition

### Why JC?

[jc (JSON Convert)](https://github.com/kellyjonbrazil/jc) provides:
- **240+ parsers** for Unix commands
- **Robust parsing** of complex output formats
- **Consistent schemas** across different platforms
- **Streaming parsers** for some commands (e.g., `--ls-s`, `--ping-s`)

We use jc as an external dependency, calling it via subprocess to maintain:
- **Process isolation** and automatic backpressure
- **True streaming** with OS pipe buffers
- **SIGPIPE propagation** for early termination

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
# dependencies = ["jc>=1.23.0"]
# [tool.jn]
# matches = ["^ls($| )", "^ls .*"]
# ///

"""
JN Shell Plugin: ls

Execute `ls` command and convert output to NDJSON using jc parser.

Usage:
    jn cat ls
    jn cat "ls -l"
    jn sh ls -la /tmp

Output schema: (from jc --ls)
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
import shutil
import shlex


def reads(command_str=None):
    """Execute ls command and stream NDJSON records."""
    if not command_str:
        command_str = "ls"

    # Check if jc is available
    if not shutil.which('jc'):
        error = {"_error": "jc not found. Install: pip install jc"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    # Parse command string safely
    try:
        args = shlex.split(command_str)
    except ValueError as e:
        error = {"_error": f"Invalid command syntax: {e}"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    # Validate command
    if not args or args[0] != 'ls':
        error = {"_error": f"Expected ls command, got: {command_str}"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    # Choose jc parser (streaming if available)
    has_long_flag = any(arg.startswith('-') and 'l' in arg for arg in args[1:])
    jc_parser = '--ls-s' if has_long_flag else '--ls'
    jc_cmd = ['jc', jc_parser]

    try:
        # Chain: ls [args] | jc
        ls_proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=sys.stderr
        )

        jc_proc = subprocess.Popen(
            jc_cmd,
            stdin=ls_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1  # Line buffered
        )

        # CRITICAL: Close ls stdout in parent to enable SIGPIPE propagation
        ls_proc.stdout.close()

        # Stream output
        if has_long_flag:
            # Streaming parser: outputs NDJSON directly
            for line in jc_proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
        else:
            # Non-streaming: convert JSON array to NDJSON
            output = jc_proc.stdout.read()
            records = json.loads(output) if output.strip() else []
            for record in records:
                print(json.dumps(record))

        # Wait for both processes
        jc_proc.wait()
        ls_proc.wait()

    except BrokenPipeError:
        # Downstream closed (e.g., head -n 10) - expected
        pass
    except KeyboardInterrupt:
        # User interrupted
        pass


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

#### 1. Regex Pattern Matching
```python
# [tool.jn]
# matches = ["^ls($| )", "^ls .*"]
```

- `^ls($| )` - Matches "ls" alone or "ls " followed by anything
- `^ls .*` - Matches "ls " followed by any arguments
- Pattern resolves to this specific plugin when user types `jn cat ls` or `jn sh ls`

#### 2. shlex for Safe Parsing
```python
args = shlex.split(command_str)  # "find . -name '*.py'" → ['find', '.', '-name', '*.py']
```

Never use `shell=True` in subprocess calls - it's a security risk.

#### 3. SIGPIPE Propagation
```python
ls_proc.stdout.close()  # CRITICAL for backpressure!
```

Closing stdout in the parent process enables SIGPIPE to propagate backward through the pipeline when downstream processes terminate (e.g., `head -n 10`).

#### 4. Streaming vs Batch Parsers

**Streaming parsers** (e.g., `jc --ls-s`, `jc --ping-s`):
- Output NDJSON directly (one object per line)
- Can be written directly to stdout
- Memory usage stays constant
- First results appear immediately

**Batch parsers** (e.g., `jc --ls`, `jc --ps`):
- Output JSON array
- Must be converted to NDJSON in our plugin
- Entire command must complete before output

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

| Plugin | Command | JC Parser | Streaming | Description |
|--------|---------|-----------|-----------|-------------|
| `ls_shell.py` | `ls` | `--ls` / `--ls-s` | Yes (with -l) | Directory listings |
| `ps_shell.py` | `ps` | `--ps` | No | Process information |
| `env_shell.py` | `env` | `--env` | No | Environment variables |
| `find_shell.py` | `find` | `--find` | No | File search |
| `tail_shell.py` | `tail` | (none) | Yes | File tail/follow |

**Note:** `tail_shell.py` doesn't use jc - it wraps each line as a simple JSON object with metadata.

## Next Shell Commands to Implement

Based on the jc project and common Unix usage patterns, these are the next priority shell commands:

### 1. du - Disk Usage
**Use case:** Find large directories consuming disk space

**JC Parser:** `jc --du`

**Output schema:**
```json
{
  "size": integer,      // Size in blocks or bytes
  "name": string        // Directory/file path
}
```

**Example:**
```bash
jn sh du -h /var/log | jn filter '.size > 1000000'
```

### 2. df - Disk Free
**Use case:** Monitor filesystem usage

**JC Parser:** `jc --df`

**Output schema:**
```json
{
  "filesystem": string,
  "size": integer,           // Total size
  "used": integer,
  "available": integer,
  "capacity_percent": integer,
  "mounted_on": string
}
```

**Example:**
```bash
jn sh df -h | jn filter '.capacity_percent > 80'
```

### 3. who - Logged In Users
**Use case:** Security monitoring, see who's logged in

**JC Parser:** `jc --who`

**Output schema:**
```json
{
  "user": string,
  "tty": string,
  "time": string,
  "idle": string,
  "pid": integer,
  "from": string
}
```

**Example:**
```bash
jn sh who -a | jn filter '.user == "root"'
```

### 4. uptime - System Uptime
**Use case:** Monitor system load and uptime

**JC Parser:** `jc --uptime`

**Output schema:**
```json
{
  "time": string,
  "uptime": string,
  "uptime_days": integer,
  "uptime_hours": integer,
  "users": integer,
  "load_1m": float,
  "load_5m": float,
  "load_15m": float
}
```

**Example:**
```bash
jn sh uptime | jn filter '.load_1m > 2.0'
```

### 5. netstat - Network Connections
**Use case:** Troubleshoot network issues, monitor connections

**JC Parser:** `jc --netstat`

**Output schema:**
```json
{
  "proto": string,
  "local_address": string,
  "foreign_address": string,
  "state": string,
  "pid": integer,
  "program_name": string
}
```

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
CPU2:    ███ jc
CPU3:       ███ filter
CPU4:          ███ write
```

All 4 processes run simultaneously on different CPUs.

## Implementation Guidelines

### When Creating New Shell Plugins

1. **Check jc support first:**
   ```bash
   jc --help | grep command-name
   ```

2. **Test jc parser locally:**
   ```bash
   command args | jc --command-name
   ```

3. **Copy ls_shell.py as template** - it has the correct pattern

4. **Update these sections:**
   - `matches` regex pattern
   - Command validation (`args[0] != 'command'`)
   - JC parser name (`jc --command-name`)
   - Documentation and schema

5. **Test with backpressure:**
   ```bash
   jn sh command args | head -n 5  # Should terminate early
   ```

### When jc Doesn't Have a Parser

For commands without jc support (like `tail`):
1. Execute command directly
2. Wrap each output line in JSON
3. Add minimal metadata (line numbers, timestamps, etc.)
4. Stream line-by-line

**Example:** See `tail_shell.py:100-108`

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

### Trust jc
We trust jc to parse command output safely. It's a mature project with 240+ parsers and active maintenance.

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

## Future Enhancements

### Streaming Optimizations
- Auto-detect streaming jc parsers (`--command-s` variants)
- Use streaming parsers when available for lower latency

### Error Handling
- Better error messages for missing jc
- Parse jc error output for user-friendly messages
- Handle command not found gracefully

### Platform Support
- Test on macOS, Linux, BSD
- Handle platform-specific command variations (e.g., `ps aux` vs `ps -ef`)
- Graceful degradation when commands unavailable

## References

- **jc Project:** https://github.com/kellyjonbrazil/jc
- **jc Parsers:** https://github.com/kellyjonbrazil/jc/tree/master/jc/parsers
- **JN Architecture:** `spec/arch/design.md`
- **Backpressure Design:** `spec/arch/backpressure.md`
