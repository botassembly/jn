# Follow Mode & Continuous Streaming Analysis

## Overview

JN's subprocess-based architecture naturally supports **infinite streaming** through follow modes. This document analyzes how `tail -f`, directory watching, and other continuous data sources integrate with JN's backpressure model.

## `tail -f` - File Following

### How It Works

```bash
jn cat "shell://tail?path=/var/log/app.log&follow=true" | jn filter '.level == "ERROR"'
```

**Flow:**
1. `tail_shell.py` spawns: `tail -f /var/log/app.log`
2. For each new line, convert to NDJSON: `{"line": "...", "path": "..."}`
3. Write to stdout → OS pipe → consumer
4. Repeat indefinitely until interrupted

### Backpressure Behavior

**Scenario:** Slow consumer (e.g., writing to slow disk)

```python
# In tail_shell.py reads() function
for line in tail_proc.stdout:
    record = {"line": line.rstrip(), "path": path}
    print(json.dumps(record))  # ← BLOCKS if downstream is slow!
    sys.stdout.flush()
```

**What happens:**
1. `print()` writes to stdout pipe buffer (~64KB)
2. If consumer is slow, pipe buffer fills
3. `print()` blocks (waits for buffer space)
4. Python process blocked → doesn't read from `tail` stdout
5. `tail` stdout pipe fills (~64KB)
6. `tail` process blocks on write syscall
7. **Result:** `tail` pauses reading file until consumer catches up

**Memory:** Constant ~1MB. No accumulation, no data loss.

### Termination Modes

#### 1. User Interrupt (Ctrl+C)
```bash
jn cat "shell://tail?path=/var/log/app.log&follow=true"
# Press Ctrl+C
```

- Python receives SIGINT
- Cleans up subprocess
- `tail` process terminated
- **Graceful shutdown**

#### 2. Downstream Closes Pipe
```bash
jn cat "shell://tail?path=/var/log/app.log&follow=true" | head -n 100
```

- `head` reads 100 lines and exits
- OS closes pipe, sends SIGPIPE
- Python's stdout write fails
- Plugin exits (or catches BrokenPipeError)
- `tail` process terminated
- **Early termination works!**

#### 3. File Deleted/Rotated
```bash
# Use tail -F (--follow=name) instead of -f
tail -F /var/log/app.log  # Reopens if file rotated
```

- `-f` follows file descriptor (stops if deleted)
- `-F` follows file name (reopens if recreated)
- **Use `-F` for log rotation support**

### Implementation

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = ["^shell://tail$", "^shell://tail\\?.*"]
# ///

import subprocess
import sys
import json
from urllib.parse import urlparse, parse_qs

def reads(config=None):
    """Stream file contents, optionally following."""
    path = config.get('path') if config else None
    if not path:
        print(json.dumps({"_error": "Missing required param: path"}), file=sys.stderr)
        sys.exit(1)

    follow = config.get('follow', 'false').lower() == 'true'
    lines = config.get('lines', '10')  # Initial lines to show

    cmd = ['tail']
    if follow:
        cmd.extend(['-F', '-n', lines])  # Follow by name, handle rotation
    else:
        cmd.extend(['-n', lines])
    cmd.append(path)

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=sys.stderr, text=True)
    except FileNotFoundError:
        print(json.dumps({"_error": "tail command not found"}), file=sys.stderr)
        sys.exit(1)

    try:
        for line in proc.stdout:
            record = {"line": line.rstrip(), "path": path}
            print(json.dumps(record))
            sys.stdout.flush()
    except BrokenPipeError:
        # Downstream closed pipe (e.g., head -n 10)
        pass
    except KeyboardInterrupt:
        # User pressed Ctrl+C
        pass
    finally:
        proc.terminate()
        proc.wait(timeout=1)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', default='read')
    args = parser.parse_args()

    if args.mode == 'read':
        # Parse config from stdin or environment
        reads()
```

## Directory Watching - `inotifywait`

### How It Works

```bash
jn cat "shell://inotify?path=/var/log&events=create,modify" | jn filter '.event == "CREATE"'
```

**Flow:**
1. `inotify_shell.py` spawns: `inotifywait -m -e create,modify /var/log`
2. `inotifywait` watches directory, outputs events as they occur
3. Parse event lines, convert to NDJSON
4. Stream to stdout indefinitely

### Example Output

```
# inotifywait raw output:
/var/log/ CREATE app.log.1
/var/log/ MODIFY app.log
/var/log/ DELETE old.log

# After conversion to NDJSON:
{"path": "/var/log/", "event": "CREATE", "file": "app.log.1"}
{"path": "/var/log/", "event": "MODIFY", "file": "app.log"}
{"path": "/var/log/", "event": "DELETE", "file": "old.log"}
```

### Backpressure Behavior

Same as `tail -f`:
- Slow consumer → pipe fills → Python blocks on `print()` → `inotifywait` blocks
- **Memory constant** even for thousands of events/sec

### Implementation

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = ["^shell://inotify$", "^shell://inotify\\?.*"]
# ///

import subprocess
import sys
import json
import shutil

def reads(config=None):
    """Watch directory for filesystem events."""
    path = config.get('path', '.') if config else '.'
    events = config.get('events', 'create,modify,delete').split(',')

    # Check if inotifywait is available
    if not shutil.which('inotifywait'):
        print(json.dumps({"_error": "inotifywait not found. Install: apt-get install inotify-tools"}), file=sys.stderr)
        sys.exit(1)

    # Build command: inotifywait -m -e create,modify /path
    cmd = ['inotifywait', '-m', '-e', ','.join(events), path]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=sys.stderr, text=True, bufsize=1)
    except FileNotFoundError:
        print(json.dumps({"_error": "inotifywait command not found"}), file=sys.stderr)
        sys.exit(1)

    try:
        for line in proc.stdout:
            # Parse: "/var/log/ CREATE file.txt"
            parts = line.strip().split(None, 2)
            if len(parts) >= 3:
                record = {
                    "path": parts[0],
                    "event": parts[1],
                    "file": parts[2] if len(parts) > 2 else None
                }
                print(json.dumps(record))
                sys.stdout.flush()
    except BrokenPipeError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        proc.wait(timeout=1)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', default='read')
    args = parser.parse_args()

    if args.mode == 'read':
        reads()
```

### Use Cases

**1. Watch for new log files:**
```bash
jn cat "shell://inotify?path=/var/log&events=create" | \
  jn filter '.file | endswith(".log")' | \
  jn run tail_shell.py
```

**2. Auto-process uploads:**
```bash
jn cat "shell://inotify?path=/uploads&events=close_write" | \
  jn filter '.file | endswith(".csv")' | \
  jn run process_upload.py
```

**3. Build system watching:**
```bash
jn cat "shell://inotify?path=./src&events=modify" | \
  jn filter '.file | endswith(".py")' | \
  jn run run_tests.py
```

## Other Continuous Sources

### `top -b` - Continuous Process Monitoring

```bash
jn cat "shell://top?delay=1&iterations=0" | jn filter '.cpu_percent > 80'
```

- `top -b -d 1` outputs snapshots every 1 second
- `iterations=0` means infinite
- Each snapshot converted to NDJSON records

### `ping` - Continuous Network Testing

```bash
jn cat "shell://ping?host=example.com&count=0" | jn filter '.time_ms > 100'
```

- `ping -c 0` means infinite pings (or omit `-c`)
- jc has `--ping-s` streaming parser
- Each ping result → NDJSON record

### `vmstat`/`iostat` - System Metrics

```bash
jn cat "shell://vmstat?delay=1&count=0" | jn filter '.free_memory < 1000000'
```

- Outputs system metrics at intervals
- Streaming parsers available in jc

## Constraints & Considerations

### 1. Process Lifetime

**Constraint:** Follow-mode plugins run indefinitely until interrupted.

**Implications:**
- Must handle cleanup properly (terminate subprocess)
- Must handle signals (SIGINT, SIGPIPE)
- Resource leaks if not careful

### 2. Buffer Management

**Constraint:** OS pipes have limited buffer (~64KB).

**Implications:**
- If consumer stops, producer blocks (desired behavior!)
- No unlimited memory growth
- Backpressure automatic

### 3. Data Loss Scenarios

**When data CAN be lost:**
- File grows faster than consumer processes (tail keeps up, but if you restart you miss data)
- Directory events fire faster than buffer allows (inotify queue overflow)

**Prevention:**
- For critical logs, use separate logging infrastructure
- For event watching, increase inotify queue: `sysctl fs.inotify.max_queued_events=32768`

### 4. Cross-Platform Support

**Linux:**
- `inotifywait` (inotify-tools package)
- Excellent support

**macOS:**
- Use `fswatch` instead of `inotifywait`
- Slightly different output format

**Windows:**
- No native `tail -f` equivalent
- Use `Get-Content -Wait` (PowerShell)
- Python's `watchdog` library for directory watching

## Testing Follow Mode

### Manual Testing

```bash
# Terminal 1: Generate log entries
for i in {1..100}; do echo "Log entry $i" >> /tmp/test.log; sleep 0.1; done

# Terminal 2: Follow with JN
jn cat "shell://tail?path=/tmp/test.log&follow=true"

# Should see entries appear in real-time
```

### Automated Testing

```python
import subprocess
import time
import tempfile
import os

def test_tail_follow():
    # Create temp file
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        logfile = f.name
        f.write("Initial line\n")

    # Start tail -f process
    proc = subprocess.Popen(
        ['jn', 'cat', f'shell://tail?path={logfile}&follow=true'],
        stdout=subprocess.PIPE,
        text=True
    )

    # Write new lines
    with open(logfile, 'a') as f:
        for i in range(5):
            f.write(f"New line {i}\n")
            f.flush()
            time.sleep(0.1)

    # Read output
    lines = []
    for _ in range(5):
        line = proc.stdout.readline()
        if line:
            lines.append(line)

    # Cleanup
    proc.terminate()
    proc.wait(timeout=1)
    os.unlink(logfile)

    # Verify
    assert len(lines) >= 5, f"Expected at least 5 lines, got {len(lines)}"
```

### Backpressure Testing

```bash
# Generate fast log entries
while true; do echo "Fast log entry" >> /tmp/fast.log; done &
PID=$!

# Consume slowly (1 line per second)
jn cat "shell://tail?path=/tmp/fast.log&follow=true" | \
  while read line; do echo "$line"; sleep 1; done

# Monitor memory usage of tail_shell.py process
# Should stay constant (~1-2MB) even though log growing fast

kill $PID
```

## Conclusion

**Follow mode constraints:**
1. **Runs indefinitely** - Until interrupted or downstream closes
2. **Backpressure automatic** - OS pipes handle flow control
3. **Constant memory** - No buffering beyond pipe buffers
4. **Graceful termination** - Handles SIGINT, SIGPIPE correctly

**What you CAN do:**
- ✅ Follow log files (`tail -f`)
- ✅ Watch directories (`inotifywait`)
- ✅ Stream continuous metrics (`vmstat`, `iostat`, `top`)
- ✅ Monitor network (`ping`, `netstat` in loop)
- ✅ Compose with filters (`| jn filter`, `| head -n 10`)

**What you CANNOT do:**
- ❌ Replay missed data (if you weren't watching when event occurred)
- ❌ Buffer unlimited data in memory (by design!)
- ❌ Guarantee every event captured (inotify can overflow)

**Bottom line:** JN's subprocess architecture is **perfect** for infinite streaming. Backpressure is automatic, memory is constant, and early termination works correctly. Follow modes are first-class citizens in JN pipelines.
