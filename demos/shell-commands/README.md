# Shell Commands Demo

This demo shows how to convert shell command output into NDJSON format for filtering and analysis.

## What You'll Learn

- Converting shell commands to NDJSON
- Filtering system information
- Monitoring processes and resources
- Combining shell output with JN pipelines

## How It Works

JN's `jn sh` command uses `jc` (JSON Convert) to parse output from 70+ standard Unix commands:

```bash
jn sh "ls -la"      # List files as NDJSON
jn sh "ps aux"      # Process list as NDJSON
jn sh "df -h"       # Disk usage as NDJSON
```

## Supported Commands

Common commands that work with `jn sh`:

- **File operations**: `ls`, `stat`, `file`, `tree`
- **Process info**: `ps`, `top`, `lsof`
- **Network**: `ping`, `netstat`, `ss`, `dig`, `route`, `iptables`
- **System info**: `df`, `du`, `mount`, `free`, `uptime`, `uname`
- **Users**: `who`, `w`, `last`, `id`, `groups`
- **Package managers**: `apt list`, `pip list`, `npm list`
- **Other**: `env`, `date`, `crontab -l`

See [jc documentation](https://kellyjonbrazil.github.io/jc/) for the full list.

## Basic Examples

### List Files

```bash
# Get all files in current directory
jn sh "ls -la"

# Filter for large files (>1MB)
jn sh "ls -la" | jn filter '(.size | tonumber) > 1048576'

# Get Python files only
jn sh "ls -la" | jn filter '.filename | endswith(".py")'
```

### Process Information

```bash
# Get all processes
jn sh "ps aux"

# Find high CPU processes (>10%)
jn sh "ps aux" | jn filter '(.pcpu | tonumber) > 10'

# Find Python processes
jn sh "ps aux" | jn filter '.command | contains("python")'

# Top 5 by memory usage
jn sh "ps aux" | \
  jq -s 'sort_by(.pmem | tonumber) | reverse | .[:5] | .[]' | \
  jn filter '{user: .user, pid: .pid, mem: .pmem, command: .command}'
```

### Disk Usage

```bash
# Show all mounted filesystems
jn sh "df -h"

# Find filesystems over 50% full
jn sh "df" | jn filter '(.use_percent | tonumber) > 50'

# Show only local filesystems
jn sh "df" | jn filter '.filesystem | startswith("/dev/")'
```

### Network Information

```bash
# Ping a host
jn sh "ping -c 5 google.com"

# Show network connections
jn sh "netstat -tunlp" 2>/dev/null | jn filter '.state == "LISTEN"'

# DNS lookup
jn sh "dig google.com"
```

### Environment Variables

```bash
# List all environment variables
jn sh "env"

# Find PATH-related variables
jn sh "env" | jn filter '.name | contains("PATH")'

# Get specific variable
jn sh "env" | jn filter '.name == "HOME"'
```

### System Information

```bash
# System uptime
jn sh "uptime"

# Memory info
jn sh "free -h"

# Kernel info
jn sh "uname -a"
```

## Pipeline Examples

### Find and Analyze Large Files

```bash
jn sh "ls -la" | \
  jn filter '(.size | tonumber) > 1000000' | \
  jn filter '{name: .filename, size_mb: ((.size | tonumber) / 1048576 | round)}' | \
  jn put large_files.csv
```

### Monitor Top Processes

```bash
jn sh "ps aux" | \
  jq -s 'sort_by(.pcpu | tonumber) | reverse | .[:10] | .[]' | \
  jn filter '{
    user: .user,
    pid: .pid,
    cpu: .pcpu,
    mem: .pmem,
    command: (.command | split(" ")[0])
  }' | \
  jn put top_processes.json
```

### Disk Space Report

```bash
jn sh "df" | \
  jn filter '(.use_percent | tonumber) > 0' | \
  jn filter '{
    filesystem: .filesystem,
    size: .size,
    used: .used,
    available: .available,
    use_percent: .use_percent,
    mounted_on: .mounted_on
  }' | \
  jn put disk_usage.csv
```

### Environment Configuration

```bash
jn sh "env" | \
  jn filter 'select(.name | test("^(PATH|HOME|USER|SHELL)$"))' | \
  jn filter '{variable: .name, value: .value}' | \
  jn put env_config.yaml
```

## Combining Shell and File Data

### Cross-reference Process and Config

```bash
# Get running Python processes
jn sh "ps aux" | \
  jn filter '.command | contains("python")' | \
  jn filter '{pid: .pid, command: .command}' > python_procs.ndjson

# Combine with other data
jn cat python_procs.ndjson | \
  jn filter '{process: .command, timestamp: now | todate}' | \
  jn put process_snapshot.json
```

## Run the Examples

Execute the provided script:

```bash
./run_examples.sh
```

This will:
- Show file listings
- Find high-CPU processes
- Check disk usage
- Extract environment variables
- Create example reports

## Key Features

### Streaming Output

Shell commands stream their output line-by-line:

```bash
# Only process first 10 results
jn sh "ls -la /usr/bin" | jn head -n 10
```

### Error Handling

Command errors are captured in NDJSON error records:

```json
{
  "_error": true,
  "type": "command_error",
  "message": "Command failed: ls /nonexistent"
}
```

### Custom Parsers

Create custom shell plugins for specialized commands:

```python
# jn_home/plugins/shell/mycommand_shell.py
def reads(config=None):
    # Parse custom command output
    pass
```

## Limitations

- Requires `jc` (JSON Convert) to be installed
- Only supports commands that `jc` can parse
- Interactive commands (requiring TTY) won't work
- Some commands may require sudo/elevated privileges

## Installation

Install `jc` for full functionality:

```bash
# Via pip
pip install jc

# Via apt (Debian/Ubuntu)
apt install jc

# Via brew (macOS)
brew install jc
```

## Next Steps

- See the CSV demo for data transformation techniques
- Check the HTTP demo for fetching API data
- Explore combining shell data with external APIs
