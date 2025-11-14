# Tail File Follower Plugin

## What
Follow (tail -f) log files and stream new lines as NDJSON. Real-time log monitoring in pipelines.

## Why
Log monitoring and real-time data processing. Enable filtering and alerting on log streams.

## Key Features
- Follow file and stream new lines (like `tail -f`)
- Parse log formats (JSON logs, syslog, Apache, nginx)
- Multiple file following (with file name context)
- Stop on pattern match or timeout
- Handle file rotation
- Binary file detection and skip

## Dependencies
- Python stdlib (`select`, `os.stat` for polling)
- Optional: `python-dateutil` for timestamp parsing

## Examples
```bash
# Follow single log file
jn tail /var/log/app.log | jn filter '.level == "ERROR"' | jn jtbl

# Follow and parse JSON logs
jn tail /var/log/app.json | jn filter '.status >= 500' | jn put alerts.json

# Multiple files with context
jn tail /var/log/*.log | jn filter '.severity == "critical"' | jn jtbl

# Stop after pattern match
jn tail /var/log/deploy.log --until "Deployment complete"

# Follow with timeout
jn tail /var/log/app.log --timeout 60
```

## Record Structure
```json
{
  "file": "/var/log/app.log",
  "line": "2024-01-15 10:30:00 ERROR Database connection failed",
  "timestamp": "2024-01-15T10:30:00Z",
  "line_number": 12345
}
```

For JSON logs, merge log content:
```json
{
  "file": "/var/log/app.json",
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "ERROR",
  "message": "Database connection failed",
  "line_number": 12345
}
```

## URL Syntax
- `tail:///var/log/app.log` - Follow single file
- `tail:///var/log/*.log` - Follow multiple files (glob)
- `tail:///var/log/app.log?timeout=60` - Auto-stop after 60s
- `tail:///var/log/app.log?until=pattern` - Stop on pattern

## Out of Scope
- Interactive terminal control - streaming only
- Log rotation handling (inotify) - use watchdog plugin
- Complex log parsing (multiline stack traces) - basic line-by-line
