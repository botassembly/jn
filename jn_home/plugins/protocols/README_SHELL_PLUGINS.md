# Shell Command Plugins for JN

## Overview

Shell command plugins bring the power of Unix utilities into JN's streaming pipeline architecture. Inspired by [jc (JSON Convert)](https://github.com/kellyjonbrazil/jc), these plugins execute common shell commands and convert their output to NDJSON, enabling composable data pipelines.

**Philosophy:** Incorporate, don't replace. Wrap battle-tested Unix utilities with thin Python adapters that handle streaming and backpressure correctly.

## Quick Start

```bash
# List files in a directory
jn cat shell://ls?path=/tmp

# Find Python files larger than 100KB
jn cat "shell://find?path=.&name=*.py" | jn filter '.size > 100000'

# Monitor processes using high CPU
jn cat shell://ps | jn filter '.cpu_percent > 50'

# Follow a log file in real-time
jn cat "shell://tail?path=/var/log/syslog&follow=true" | jn filter '.level == "ERROR"'

# List environment variables containing "PATH"
jn cat shell://env | jn filter '.name | contains("PATH")'
```

## Available Plugins

### 1. `ls_shell.py` - Directory Listing

List directory contents with optional long format.

**URL Pattern:** `shell://ls?path=<dir>&long=<bool>&all=<bool>`

**Parameters:**
- `path` - Directory to list (default: current directory)
- `long` - Use long format with details (default: false)
- `all` - Show hidden files (default: false)
- `recursive` - Recursive listing (default: false)

**Examples:**
```bash
# Basic listing
jn cat shell://ls

# Long format with details
jn cat "shell://ls?path=/var/log&long=true"

# Show hidden files
jn cat "shell://ls?path=/home/user&all=true"

# Backpressure: Only list first 10 files
jn cat "shell://ls?path=/usr/bin&long=true" | head -n 10
```

**Output Schema (long format):**
```json
{
  "filename": "test.txt",
  "flags": "-rw-r--r--",
  "links": 1,
  "owner": "user",
  "group": "user",
  "size": 1234,
  "date": "Nov 12 10:30"
}
```

### 2. `find_shell.py` - File Search

Recursively find files matching criteria.

**URL Pattern:** `shell://find?path=<dir>&name=<pattern>&type=<f|d|l>`

**Parameters:**
- `path` - Starting directory (default: current directory)
- `name` - Filename pattern (e.g., "*.py", "README*")
- `type` - File type: `f` (file), `d` (directory), `l` (symlink)
- `maxdepth` - Maximum depth to descend
- `mindepth` - Minimum depth to descend
- `size` - Size filter (e.g., "+1M", "-100k")
- `mtime` - Modified time (e.g., "-7" for last 7 days)

**Examples:**
```bash
# Find all Python files
jn cat "shell://find?path=.&name=*.py"

# Find files modified in last 7 days
jn cat "shell://find?path=/var/log&mtime=-7&type=f"

# Find large files (>100MB)
jn cat "shell://find?path=/home&size=+100M"

# Find and filter
jn cat "shell://find?path=.&name=*.txt" | jn filter '.path | contains("test")'
```

**Output Schema:**
```json
{
  "path": "./src",
  "node": "main.py"
}
```

### 3. `ps_shell.py` - Process Listing

List running processes with details.

**URL Pattern:** `shell://ps?full=<bool>&user=<username>&pid=<id>`

**Parameters:**
- `full` - Use full format (default: true)
- `user` - Filter by username
- `pid` - Filter by process ID

**Examples:**
```bash
# List all processes
jn cat shell://ps

# Filter high CPU processes
jn cat shell://ps | jn filter '.cpu_percent > 50'

# Find Python processes
jn cat shell://ps | jn filter '.cmd | contains("python")'

# Processes for specific user
jn cat "shell://ps?user=root"
```

**Output Schema:**
```json
{
  "uid": "root",
  "pid": 1234,
  "ppid": 1,
  "cpu_percent": 5.2,
  "mem_percent": 2.1,
  "vsz": 123456,
  "rss": 45678,
  "cmd": "/usr/bin/python3 app.py"
}
```

### 4. `tail_shell.py` - File Following

Stream file contents, with optional follow mode for continuous monitoring.

**URL Pattern:** `shell://tail?path=<file>&follow=<bool>&lines=<n>`

**Parameters:**
- `path` - File to tail (required)
- `follow` - Follow file as it grows (default: false)
- `lines` - Number of initial lines to show (default: 10)

**Examples:**
```bash
# Show last 10 lines
jn cat "shell://tail?path=/var/log/syslog"

# Follow log file in real-time
jn cat "shell://tail?path=/var/log/app.log&follow=true"

# Filter errors from live log
jn cat "shell://tail?path=/var/log/app.log&follow=true" | \
  jn filter '.line | contains("ERROR")'

# Show last 50 lines
jn cat "shell://tail?path=/var/log/messages&lines=50"
```

**Output Schema:**
```json
{
  "line": "2025-11-13 10:30:45 ERROR Connection failed",
  "path": "/var/log/app.log",
  "line_number": 42
}
```

**Follow Mode Notes:**
- Uses `tail -F` which handles log rotation
- Runs indefinitely until interrupted (Ctrl+C) or pipe closed
- Automatic backpressure: if downstream is slow, tail blocks
- Constant memory regardless of file size or growth rate

### 5. `env_shell.py` - Environment Variables

List all environment variables.

**URL Pattern:** `shell://env`

**Examples:**
```bash
# List all environment variables
jn cat shell://env

# Find PATH variable
jn cat shell://env | jn filter '.name == "PATH"'

# Find variables containing "PYTHON"
jn cat shell://env | jn filter '.name | contains("PYTHON")'

# Export to CSV
jn cat shell://env | jn put env_vars.csv
```

**Output Schema:**
```json
{
  "name": "PATH",
  "value": "/usr/local/bin:/usr/bin:/bin"
}
```

## Backpressure & Streaming

All shell plugins support automatic backpressure via OS pipes:

```bash
# Only processes first 10 files, not entire directory
jn cat "shell://ls?path=/usr/bin" | head -n 10

# Only finds first 5 matches, stops searching
jn cat "shell://find?path=/usr" | head -n 5

# Slow consumer automatically slows down tail -f
jn cat "shell://tail?path=/var/log/huge.log&follow=true" | \
  while read line; do echo "$line"; sleep 1; done
```

**How it works:**
1. Consumer reads slowly → OS pipe buffer fills
2. Plugin blocks on write → shell command blocks
3. No memory accumulation, no data loss
4. Early termination works correctly (SIGPIPE)

## Architecture

Each plugin:
1. Spawns shell command as subprocess (secure, no shell injection)
2. Pipes output to `jc` for parsing
3. Converts to NDJSON for streaming
4. Handles cleanup and signals properly

```python
# Simplified example
ls_proc = subprocess.Popen(['ls', '-l', path], stdout=PIPE)
jc_proc = subprocess.Popen(['jc', '--ls-s'], stdin=ls_proc.stdout, stdout=PIPE)

# CRITICAL: Enable SIGPIPE propagation
ls_proc.stdout.close()

# Stream output
for line in jc_proc.stdout:
    print(line)
```

## Installation Requirements

All shell plugins require:

**Python packages:**
```bash
pip install jc>=1.23.0
```

**System commands:**
- `ls`, `find`, `ps`, `tail` - Standard on all Unix systems
- `jc` - Install via pip (provides JSON parsing)

## Error Handling

Plugins handle errors gracefully:

```bash
# Nonexistent path
$ jn cat "shell://ls?path=/nonexistent"
{"_error": "Path not found: /nonexistent", "path": "/nonexistent"}

# Permission denied (in find)
$ jn cat "shell://find?path=/root"
{"path": null, "node": null, "error": "find: '/root': Permission denied"}
```

## Testing

Comprehensive test suite included:

```bash
# Run all shell plugin tests
pytest tests/test_shell_plugins.py -v

# Test specific plugin
pytest tests/test_shell_plugins.py::TestLsPlugin -v

# Test backpressure behavior
pytest tests/test_shell_plugins.py::TestBackpressure -v
```

## Performance Characteristics

**Memory:** Constant ~1-5MB per plugin, regardless of data size

**CPU:** True parallelism - each stage runs on separate CPU
```
CPU1: ████ ls        CPU2:   ████ jc
CPU3:     ████ filter CPU4:       ████ writer
All stages run simultaneously!
```

**Latency:** Immediate - first output in milliseconds, no buffering

## Future Plugins

Additional shell commands planned:
- `du_shell.py` - Disk usage analysis
- `df_shell.py` - Filesystem capacity
- `stat_shell.py` - Detailed file statistics
- `lsof_shell.py` - Open files and handles
- `netstat_shell.py` - Network connections
- `ping_shell.py` - Network diagnostics
- `dig_shell.py` - DNS lookups
- `ip_shell.py` - Network interfaces
- `inotify_shell.py` - Directory watching

## Contributing

To add a new shell plugin:

1. **Create plugin file:** `jn_home/plugins/protocols/<command>_shell.py`
2. **Add URL pattern:** `matches = ["^shell://<command>$", "^shell://<command>\\?.*"]`
3. **Implement reads():** Execute command, pipe to jc, stream NDJSON
4. **Add tests:** `tests/test_shell_plugins.py`
5. **Update docs:** This README

**Template:**
```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["jc>=1.23.0"]
# [tool.jn]
# matches = ["^shell://mycommand$", "^shell://mycommand\\?.*"]
# ///

def reads(config=None):
    # 1. Parse config parameters
    # 2. Build command list (no shell=True!)
    # 3. Chain: cmd | jc
    # 4. Stream NDJSON output
    # 5. Handle errors and cleanup
    pass
```

## References

- [jc (JSON Convert)](https://github.com/kellyjonbrazil/jc) - Inspiration and parsing engine
- [JN Architecture](../../spec/arch/design.md) - Core framework design
- [Backpressure Explanation](../../spec/arch/backpressure.md) - Why Popen > async
- [Shell Plugins Design](../../spec/arch/shell-plugins.md) - Detailed architecture
- [Follow Mode Analysis](../../spec/arch/follow-mode-analysis.md) - Streaming & following

## License

Same as JN project (see root LICENSE file).
