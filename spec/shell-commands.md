# Shell Commands - Design Document

## Overview

Shell command support in JN uses a **fallback architecture**: custom plugins are checked first, then jc (JSON Convert) acts as a universal fallback for 240+ Unix commands.

**Philosophy:** Incorporate, don't replace. Use jc's battle-tested parsers as a fallback, write custom plugins only when needed.

## Architecture

### Two-Tier Resolution

```
User types: jn sh ls -l

1. Check custom plugins (jn_home/plugins/shell/*.py)
   └─> If match found: Execute custom plugin

2. If no match: Check jc fallback
   └─> If jc supports command: Execute command | jc --command

3. If jc doesn't support: Error
```

**Priority:**
```
Custom plugins > jc fallback > error
```

### jc as Core Dependency

jc is a **core framework dependency** (in `pyproject.toml`), not a plugin:
- Installed with: `pip install jn` (includes jc automatically)
- Fallback logic lives in: `src/jn/shell/jc_fallback.py`
- Integrated into: `src/jn/cli/commands/sh.py`

### Plugin Directory Structure

```
jn_home/plugins/shell/
  └── tail_shell.py     # Custom plugin (jc doesn't do what we want)

(No ls, ps, env, find plugins - jc handles these!)
```

Custom plugins are **only needed** when:
1. jc doesn't support the command
2. You want different behavior than jc provides
3. Output is trivial enough that jc adds overhead

## How jc Fallback Works

### Core Pattern: Command → jc → NDJSON

When no custom plugin matches:

```
Unix Command → jc parser → NDJSON output
```

1. **Execute the command** as subprocess
2. **Pipe to jc** with appropriate parser (e.g., `jc --ls`)
3. **Convert to NDJSON** (jc streaming parsers output NDJSON; batch parsers output JSON arrays)
4. **Stream to stdout** for pipeline composition

### Code Flow

```python
# src/jn/cli/commands/sh.py

# Try custom plugin first
stages = resolver.plan_execution(addr, mode="read")

if not stages:
    # No custom plugin - try jc fallback
    if supports_command(command_name):
        exit_code = execute_with_jc(command_str)  # src/jn/shell/jc_fallback.py
        sys.exit(exit_code)
    else:
        # jc doesn't support it either
        error("No plugin or jc parser found")
```

### Streaming vs Batch Parsers

**jc has two parser types:**

**Streaming parsers** (output NDJSON directly):
- `--ls-s`, `--ping-s`, `--dig-s`, `--traceroute-s`
- Output one JSON object per line
- Zero memory accumulation
- First results appear immediately

**Batch parsers** (output JSON array):
- `--ls`, `--ps`, `--df`, `--du`, etc.
- Output `[{...}, {...}]` after command completes
- We convert to NDJSON in fallback logic

Both support **full backpressure** via OS pipes.

## Command Invocation

### Via `jn sh` (Recommended)
```bash
jn sh ls -l /tmp          # jc fallback
jn sh ps aux              # jc fallback
jn sh df -h               # jc fallback
jn sh tail -f /var/log    # Custom plugin (if exists)

# Graceful ls fallback
# If you run `jn sh ls` without `-l`, JN will automatically
# use jc's batch `--ls` parser and output filenames-only NDJSON.
# Add `-l` (e.g., `jn sh ls -l`) to get full metadata via streaming.
```

### Via `jn cat` (Quoted)
```bash
jn cat "ls -l /tmp"
jn cat "ps aux"
```

Both work identically.

## Supported Commands

### Via jc Fallback (240+ commands)

jc supports a huge range of Unix commands. Here are some highlights:

**System Info:**
- `ps`, `uptime`, `uname`, `who`, `w`, `id`, `last`

**Filesystems:**
- `ls`, `df`, `du`, `mount`, `lsblk`, `findmnt`

**Networking:**
- `ifconfig`, `ip`, `netstat`, `ss`, `arp`, `route`, `ping`, `dig`, `traceroute`

**Process/Performance:**
- `top`, `vmstat`, `iostat`, `mpstat`, `free`, `sar`

**System Management:**
- `systemctl`, `timedatectl`, `sysctl`, `dmidecode`

**Package Management:**
- `apt-cache`, `yum`, `dpkg`, `rpm`

**Files:**
- `file`, `stat`, `lsof`, `find`

**Config Files:**
- `/etc/hosts`, `/etc/fstab`, `/etc/passwd`, `/etc/group`, `iptables-save`

**And 200+ more!**

See full list: https://github.com/kellyjonbrazil/jc#parsers

### Via Custom Plugins

Currently only:
- `tail` - Stream file contents line-by-line (jc doesn't support streaming file tails)
- `watchfiles` - Watch a directory and emit filesystem change events

Add more custom plugins as needed for commands jc doesn't support.

## JSON Schemas (from jc)

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
  "link_to": "target"
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

### df
```json
{
  "filesystem": "/dev/sda1",
  "size": 1048576,
  "used": 524288,
  "available": 524288,
  "capacity_percent": 50,
  "mounted_on": "/"
}
```

### du
```json
{
  "size": 104608,
  "name": "/usr/bin"
}
```

### env
```json
{
  "name": "PATH",
  "value": "/usr/local/bin:/usr/bin:/bin"
}
```

### tail (custom plugin)
```json
{
  "line": "Log message here",
  "line_number": 42
}
```

All schemas documented at: https://github.com/kellyjonbrazil/jc/tree/master/jc/parsers

## Creating Custom Plugins

### When to Create a Custom Plugin

Only create a custom plugin when:

1. **jc doesn't support the command**
   - Check first: `jc --help | grep commandname`

2. **You need different behavior than jc**
   - Example: tail needs true streaming, not jc's line wrapping

3. **Output is trivial**
   - Example: Just wrapping paths, no parsing needed

### Custom Plugin Template

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []  # No jc dependency in plugins!
# [tool.jn]
# matches = ["^tail($| )", "^tail .*"]
# ///

"""
JN Shell Plugin: tail

Custom plugin for tail - provides true streaming support.

Usage:
    jn sh tail -f /var/log/syslog
    jn sh tail -n 100 /var/log/app.log
"""

import subprocess
import sys
import json
import shlex


def reads(command_str=None):
    """Execute tail and stream NDJSON records."""
    if not command_str:
        error = {"_error": "tail requires a file argument"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    # Parse command safely
    args = shlex.split(command_str)

    # Validate
    if args[0] != 'tail':
        error = {"_error": f"Expected tail, got: {args[0]}"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    # Execute command
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        bufsize=1  # Line buffered
    )

    # Stream line-by-line
    line_number = 0
    for line in proc.stdout:
        line_number += 1
        record = {
            "line": line.rstrip(),
            "line_number": line_number
        }
        print(json.dumps(record))
        sys.stdout.flush()

    proc.wait()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', default='read')
    parser.add_argument('address', nargs='?')
    args = parser.parse_args()

    if args.mode == 'read':
        reads(args.address)
```

### Plugin Guidelines

1. **Match pattern**: `["^command($| )", "^command .*"]`
2. **No jc dependency** in plugin PEP 723 block
3. **Use shlex** for safe command parsing
4. **Stream line-by-line** with `sys.stdout.flush()`
5. **Handle BrokenPipeError** gracefully (downstream closes)

## Performance Characteristics

### Memory Usage
**Constant ~1MB** regardless of data size:
- OS pipe buffers (~64KB per pipe)
- Line-by-line processing
- No accumulation (even with jc batch parsers)

### Streaming Behavior
```bash
jn sh find /huge/dir -name "*.log" | head -n 5
```

- Find starts outputting immediately
- Pipes to jc (if custom plugin doesn't match)
- jc parses and outputs NDJSON
- Head terminates after 5 lines
- SIGPIPE propagates: head → jc → find
- Find stops scanning (doesn't process millions of files)

### Backpressure with jc

```
find → jc → head -n 5
(3 processes, 2 OS pipes)
```

When head closes after 5 lines:
1. OS pipe from jc to head fills → jc blocks writing
2. OS pipe from find to jc fills → find blocks writing
3. SIGPIPE propagates backward
4. All processes terminate cleanly

**No difference from custom plugins** - OS handles everything.

## Examples

### jc Fallback (No Plugin Needed)

```bash
# Disk usage over 80%
jn sh df -h | jn filter '.capacity_percent > 80'

# CPU hogs
jn sh ps aux | jn filter '.cpu_percent > 50.0'

# Large directories
jn sh du -h /var | jn filter '.size > 1000000'

# Network listeners
jn sh netstat -tulpn | jn filter '.state == "LISTEN"'

# System load
jn sh uptime | jn filter '.load_1m > 2.0'

# Environment PATH
jn sh env | jn filter '.name == "PATH"'
```

### Custom Plugin

```bash
# Tail log file (uses tail_shell.py)
jn sh tail -f /var/log/syslog | jn filter '.line | contains("error")'

# Watch a directory (uses watchfiles_shell.py)
jn sh watchfiles /var/log --exit-after 1 --initial
jn sh watchfiles ~/Downloads --recursive --debounce-ms 100
```

## Testing

### Test jc Fallback

```bash
# Check jc is installed
which jc

# Test a command
jn sh ls -l | head -5
jn sh ps aux | head -3
jn sh df -h

# Test backpressure (should terminate early)
jn sh find / -name "*.log" | head -n 10
```

### Test Custom Plugin Priority

```bash
# If you create custom ls_shell.py, it takes priority over jc
jn sh ls -l    # Uses custom plugin, not jc
```

### Test Unsupported Command

```bash
# Command jc doesn't support
jn sh unsupported_command
# Error: No plugin or jc parser found for command: unsupported_command
```

## Maintenance Strategy

### Adding New Commands

**Don't write a plugin!** Check if jc supports it first:

```bash
jc --help | grep commandname
```

If jc supports it, it works automatically:
```bash
jn sh commandname args    # Just works!
```

Only write a plugin if:
- jc doesn't support it
- You need different behavior

### When jc Updates

Since jc is a core dependency, update it regularly:

```bash
pip install --upgrade jc
```

New jc parsers are automatically available in JN (no code changes needed).

### Migration Path

If you have custom plugins that duplicate jc functionality:

1. **Test with jc**: `jn sh command | head -10`
2. **Compare output**: Does jc's schema work for you?
3. **If yes**: Delete custom plugin, use jc fallback
4. **If no**: Keep custom plugin (takes priority)

## References

- **jc Project:** https://github.com/kellyjonbrazil/jc
- **jc Parsers List:** https://github.com/kellyjonbrazil/jc#parsers
- **jc Parser Code:** https://github.com/kellyjonbrazil/jc/tree/master/jc/parsers
- **JN Architecture:** `spec/arch/design.md`
- **Backpressure Design:** `spec/arch/backpressure.md`

## Key Files

- **jc fallback logic**: `src/jn/shell/jc_fallback.py`
- **Integration**: `src/jn/cli/commands/sh.py`
- **Dependency**: `pyproject.toml` (jc>=1.23.0)
- **Custom plugins**: `jn_home/plugins/shell/*.py`
