# Shell Command Plugins - Design Document

## Overview

Inspired by [jc (JSON Convert)](https://github.com/kellyjonbrazil/jc), we're adding shell command plugins to JN. These plugins execute common shell commands and convert their output to NDJSON, enabling composable data pipelines from system utilities.

**Philosophy:** Incorporate, don't replace. Wrap battle-tested Unix utilities with thin Python adapters that handle streaming and backpressure correctly.

## Architecture

### Plugin Pattern: Command Wrapper + JC Parser

Each shell plugin:
1. **Spawns the shell command** as a subprocess (not via shell=True for security)
2. **Pipes command output** to `jc` for parsing
3. **Converts JSON arrays** to NDJSON (newline-delimited)
4. **Streams to stdout** for pipeline composition

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["jc>=1.23.0"]
# [tool.jn]
# matches = ["^shell://ls$", "^shell://ls\\?.*"]
# ///

import subprocess
import sys
import json

def reads(config=None):
    """Execute ls command and yield NDJSON records."""
    # Parse options from config (e.g., shell://ls?path=/tmp&long=true)
    path = config.get('path', '.') if config else '.'
    long_format = config.get('long', 'false').lower() == 'true'

    # Build command args (no shell=True!)
    cmd = ['ls']
    if long_format:
        cmd.append('-l')
    cmd.append(path)

    # Chain: ls | jc --ls-s (streaming parser)
    ls_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=sys.stderr)
    jc_proc = subprocess.Popen(
        ['jc', '--ls-s'],
        stdin=ls_proc.stdout,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True
    )

    # CRITICAL: Close ls stdout in parent to enable SIGPIPE propagation
    ls_proc.stdout.close()

    # Stream NDJSON output line-by-line
    for line in jc_proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()

    jc_proc.wait()
    ls_proc.wait()
```

### URL Protocol: `shell://`

Shell plugins match URLs like:
- `shell://ls` → `ls` current directory
- `shell://ls?path=/var/log` → `ls /var/log`
- `shell://ls?path=/tmp&long=true` → `ls -l /tmp`
- `shell://find?path=/home&name=*.py` → `find /home -name '*.py'`
- `shell://ps?full=true` → `ps -ef`

**Security:** Parse query params carefully. No shell injection. Use subprocess lists, not strings.

## Backpressure Behavior

### Automatic Backpressure via OS Pipes

```bash
jn cat shell://ls?path=/var/log | head -n 5
```

**What happens:**
1. `ls -l /var/log` starts producing output
2. `jc --ls-s` parses and converts to NDJSON
3. JN reads 5 records and closes stdin
4. OS sends SIGPIPE backward through pipeline
5. `jc` process terminates (broken pipe)
6. `ls` process terminates (broken pipe)
7. **Result:** Only ~5 files listed, not entire directory

**Memory:** Constant ~1MB regardless of directory size.

### Key Implementation Details

```python
# Chain processes: cmd | jc
cmd_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
jc_proc = subprocess.Popen(jc_cmd, stdin=cmd_proc.stdout, stdout=subprocess.PIPE)

# CRITICAL: Close cmd stdout in parent process!
# This enables SIGPIPE to propagate when jc exits
cmd_proc.stdout.close()

# Stream output (yields control to consumer)
for line in jc_proc.stdout:
    sys.stdout.write(line)  # Blocks if downstream pipe full!
    sys.stdout.flush()

# Wait for both processes
jc_proc.wait()
cmd_proc.wait()
```

## Priority Plugins (15 Commands)

### Tier 1: Filesystem & Processes (Most Critical)

1. **`ls_shell.py`** - Directory listing
   - Matches: `shell://ls`, `shell://ls?path=...`
   - Command: `ls -l | jc --ls-s`
   - Streaming: Yes (jc has `--ls-s`)
   - Use case: List files, feed into filters

2. **`find_shell.py`** - File search
   - Matches: `shell://find`, `shell://find?path=...&name=...`
   - Command: `find <path> -name <pattern> | jc --find`
   - Streaming: No (but find itself streams)
   - Use case: Recursive file discovery

3. **`stat_shell.py`** - File statistics
   - Matches: `shell://stat?path=...`
   - Command: `stat <files> | jc --stat-s`
   - Streaming: Yes (jc has `--stat-s`)
   - Use case: Detailed file metadata

4. **`ps_shell.py`** - Process listing
   - Matches: `shell://ps`, `shell://ps?full=true`
   - Command: `ps -ef | jc --ps` or `ps aux | jc --ps`
   - Streaming: No (snapshot)
   - Use case: System monitoring, process analysis

5. **`du_shell.py`** - Disk usage
   - Matches: `shell://du?path=...`
   - Command: `du -a <path> | jc --du`
   - Streaming: No
   - Use case: Find large files/directories

6. **`df_shell.py`** - Disk free space
   - Matches: `shell://df`
   - Command: `df -h | jc --df`
   - Streaming: No (small output)
   - Use case: System capacity monitoring

### Tier 2: System Info & Monitoring

7. **`env_shell.py`** - Environment variables
   - Matches: `shell://env`
   - Command: `env | jc --env`
   - Streaming: No (small output)
   - Use case: Configuration inspection

8. **`who_shell.py`** - Logged in users
   - Matches: `shell://who`
   - Command: `who | jc --who`
   - Streaming: No (small output)
   - Use case: Security auditing

9. **`mount_shell.py`** - Mounted filesystems
   - Matches: `shell://mount`
   - Command: `mount | jc --mount`
   - Streaming: No (small output)
   - Use case: Storage topology

10. **`lsof_shell.py`** - List open files
    - Matches: `shell://lsof`, `shell://lsof?pid=...`
    - Command: `lsof | jc --lsof` or `lsof -p <pid> | jc --lsof`
    - Streaming: No
    - Use case: Debugging file handles

11. **`top_shell.py`** - Process monitoring (snapshot)
    - Matches: `shell://top?iterations=1`
    - Command: `top -b -n 1 | jc --top-s`
    - Streaming: Yes (jc has `--top-s`)
    - Note: For continuous monitoring, use `tail -f` approach

### Tier 3: Networking

12. **`ping_shell.py`** - Network testing
    - Matches: `shell://ping?host=...&count=...`
    - Command: `ping -c <count> <host> | jc --ping-s`
    - Streaming: Yes (jc has `--ping-s`)
    - Use case: Network diagnostics

13. **`netstat_shell.py`** - Network connections
    - Matches: `shell://netstat`
    - Command: `netstat -an | jc --netstat`
    - Streaming: No (snapshot)
    - Use case: Connection monitoring

14. **`dig_shell.py`** - DNS lookup
    - Matches: `shell://dig?host=...`
    - Command: `dig <host> | jc --dig`
    - Streaming: No (single query)
    - Use case: DNS debugging

15. **`ip_shell.py`** - Network interfaces (modern)
    - Matches: `shell://ip?command=addr`
    - Command: `ip addr | jc --ip-address`
    - Streaming: No (small output)
    - Use case: Network configuration

## Special: Streaming & Following

### `tail_shell.py` - Follow files continuously

```bash
jn cat shell://tail?path=/var/log/app.log&follow=true | jn filter '.level == "ERROR"'
```

**Implementation:**
```python
def reads(config=None):
    """Stream file contents, optionally following."""
    path = config.get('path')
    follow = config.get('follow', 'false').lower() == 'true'

    cmd = ['tail']
    if follow:
        cmd.extend(['-f', '-n', '0'])  # Follow, no initial lines
    cmd.append(path)

    # tail outputs plain text, not structured
    # Either: parse as raw lines, or use jc if available
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)

    for line in proc.stdout:
        # Output as NDJSON: {"line": "...", "path": "..."}
        record = {"line": line.rstrip(), "path": path}
        print(json.dumps(record))

    proc.wait()
```

**Backpressure:**
- If downstream is slow, the loop blocks on `print()`
- OS pipe buffer fills, `tail` process blocks on write
- **Memory stays constant** even for infinite streams

### `inotify_shell.py` - Watch directories for changes

```bash
jn cat shell://inotify?path=/var/log&events=create,modify | jn filter '.event == "CREATE"'
```

**Implementation:**
```python
def reads(config=None):
    """Watch directory for filesystem events."""
    path = config.get('path', '.')
    events = config.get('events', 'create,modify').split(',')

    # Use inotifywait on Linux (or fswatch cross-platform)
    cmd = ['inotifywait', '-m', '-e', ','.join(events), path]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)

    for line in proc.stdout:
        # Parse inotifywait output: "/path/ CREATE file.txt"
        parts = line.strip().split()
        if len(parts) >= 3:
            record = {
                "path": parts[0],
                "event": parts[1],
                "file": parts[2]
            }
            print(json.dumps(record))

    proc.wait()
```

**Use case:** React to file system changes in real-time.

## Error Handling

### Command Not Found

```python
try:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
except FileNotFoundError:
    # Output error as NDJSON
    error = {"_error": f"Command not found: {cmd[0]}"}
    print(json.dumps(error), file=sys.stderr)
    sys.exit(1)
```

### Parse Errors (jc fails)

Use jc's `-qq` flag for streaming parsers:
```python
jc_cmd = ['jc', '--ls-s', '-qq']  # Ignore parse errors
```

Output includes `_jc_meta` field:
```json
{"filename": "test.txt", "_jc_meta": {"success": true}}
{"_jc_meta": {"success": false, "error": "Parse error", "line": "???"}}
```

Filter errors downstream: `jn filter '._jc_meta.success'`

## Testing Strategy

### Unit Tests

Test each plugin with:
1. **Basic invocation** - Default parameters
2. **Query params** - All supported options
3. **Backpressure** - Pipe to `head -n 5`, verify early termination
4. **Error handling** - Invalid paths, missing commands

### Integration Tests

```bash
# Test ls plugin
jn cat "shell://ls?path=/tmp" | head -n 10

# Test find plugin
jn cat "shell://find?path=/home&name=*.py" | jn filter '.size > 1000'

# Test ps plugin with filter
jn cat shell://ps | jn filter '.cpu_percent > 50'

# Test tail follow (manual - requires killing)
jn cat "shell://tail?path=/var/log/system.log&follow=true" | jn filter '.level == "ERROR"'

# Test backpressure (should only list ~5 files, not entire directory)
jn cat "shell://ls?path=/usr/bin" | head -n 5
```

### Backpressure Verification

```python
# Test that processes terminate early
import subprocess
import time

# Start pipeline: ls /usr/bin | head -n 5
proc = subprocess.Popen(
    ['jn', 'cat', 'shell://ls?path=/usr/bin'],
    stdout=subprocess.PIPE
)

# Read only 5 lines
for i in range(5):
    proc.stdout.readline()

# Close pipe (send SIGPIPE)
proc.stdout.close()
time.sleep(0.1)

# Verify process terminated (returncode is not None)
proc.poll()
assert proc.returncode is not None, "Process should have terminated due to SIGPIPE"
```

## Security Considerations

### Command Injection Prevention

**DON'T:**
```python
# NEVER use shell=True with user input!
path = config.get('path')
cmd = f"ls -l {path}"  # ❌ Injection risk!
subprocess.Popen(cmd, shell=True)
```

**DO:**
```python
# Use argument lists, not strings
path = config.get('path')
cmd = ['ls', '-l', path]  # ✅ Safe
subprocess.Popen(cmd)  # shell=False by default
```

### Path Validation

```python
import os

def reads(config=None):
    path = config.get('path', '.')

    # Validate path exists and is accessible
    if not os.path.exists(path):
        error = {"_error": f"Path not found: {path}"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    # Optionally: check path is within allowed directories
    real_path = os.path.realpath(path)
    if not real_path.startswith('/home'):  # Example restriction
        error = {"_error": f"Access denied: {path}"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)
```

## Performance Characteristics

### Memory Usage

- **Constant memory** regardless of command output size
- Typical: ~1-5MB per pipeline stage
- Buffering only in OS pipe buffers (~64KB)

### CPU Usage

- **Parallel execution** across pipeline stages
- Example: `ls | jc | filter` runs on 3 CPUs simultaneously
- GIL doesn't matter (separate processes)

### Latency

- **Immediate output** - no buffering delays
- First record appears in milliseconds
- True streaming behavior

## Dependencies

All shell plugins require:
```toml
# /// script
# dependencies = ["jc>=1.23.0"]
# ///
```

Optional system commands:
- `jc` - JSON Convert (install via `pip install jc`)
- `inotifywait` - Linux inotify tools (install via `apt-get install inotify-tools`)
- Standard Unix utilities (ls, find, ps, etc.) - typically pre-installed

## Future Enhancements

1. **Streaming by default** - Prefer `jc` streaming parsers (`--*-s`)
2. **Cross-platform** - Handle Linux/macOS/Windows command differences
3. **Rich queries** - Support complex option combinations
4. **Custom parsers** - For commands jc doesn't support
5. **Caching** - Optional result caching for expensive queries

## Example Usage

```bash
# Find large Python files
jn cat "shell://find?path=.&name=*.py" | \
  jn cat "shell://stat?path={.path}" | \
  jn filter '.size > 100000'

# Monitor process creation
jn cat "shell://ps" > /tmp/snapshot1.json
sleep 10
jn cat "shell://ps" > /tmp/snapshot2.json
# Compare snapshots...

# Watch logs for errors
jn cat "shell://tail?path=/var/log/app.log&follow=true" | \
  jn filter '.level == "ERROR"' | \
  jn put errors.json

# Network diagnostics pipeline
jn cat "shell://netstat" | \
  jn filter '.state == "ESTABLISHED"' | \
  jn cat "shell://lsof?pid={.pid}" | \
  jn put connections.csv
```

## Conclusion

Shell command plugins bring the power of Unix utilities into JN's streaming pipeline architecture. By wrapping commands with thin Python adapters and leveraging `jc` for parsing, we enable:

- **Composability** - Mix shell commands with JN transforms
- **Backpressure** - Automatic flow control via OS pipes
- **Streaming** - Constant memory for large outputs
- **Discoverability** - Standard URL protocol (`shell://`)

The result: AI agents can create data pipelines from any Unix command, with guaranteed streaming behavior and backpressure handling.
