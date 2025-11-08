# Follow Command

## Overview

Stream new lines from files as they're appended, like `tail -f`. Enables real-time processing of log files and continuously updated data files.

## Basic Usage

```bash
# Follow a file
jn follow access.log

# Follow with parser
jn follow access.log --parser apache_log_s

# Follow and filter
jn follow app.log | jq 'select(.level == "ERROR")'

# Follow and output
jn follow metrics.json | jn put influxdb://localhost/metrics
```

## Behavior

### Start Position

**Default**: Start at end of file (like `tail -f`)
```bash
jn follow access.log
# Only shows new lines appended after command starts
```

**From beginning**: Read entire file then follow
```bash
jn follow access.log --from-start
# Shows all existing lines, then continues with new ones
```

**From offset**: Start N lines from end
```bash
jn follow access.log --tail 100
# Shows last 100 lines, then continues with new ones
```

### File Rotation Handling

**Default**: Follow file descriptor (like `tail -f`)
```bash
jn follow access.log
# Stops when file is rotated/renamed
```

**Follow by name**: Continue when file is rotated (like `tail -F`)
```bash
jn follow access.log --follow-name
# Detects rotation and reopens new file
```

**Common with log rotation**:
```bash
# Log rotates: access.log → access.log.1
# Command detects, switches to new access.log
jn follow /var/log/app.log --follow-name
```

## Auto-Detection

Parser auto-detected from file extension:

```bash
jn follow data.csv        # Auto-uses csv_s streaming parser
jn follow events.json     # Auto-detects JSON lines
jn follow metrics.psv     # Auto-uses psv_s parser
```

## Options

```bash
# Parser override
jn follow file.log --parser json_s

# Start position
jn follow file.log --from-start    # Read entire file first
jn follow file.log --tail 100      # Last 100 lines, then follow

# File rotation
jn follow file.log --follow-name   # Handle rotation (like tail -F)

# Polling interval (if inotify unavailable)
jn follow file.log --poll-interval 1.0  # Check every 1 second
```

## Implementation

### Using inotify (Linux) / FSEvents (macOS)

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class FileFollower(FileSystemEventHandler):
    def __init__(self, filepath, parser):
        self.filepath = filepath
        self.parser = parser
        self.file = open(filepath, 'r')

        # Seek to end unless --from-start
        if not from_start:
            self.file.seek(0, os.SEEK_END)

    def on_modified(self, event):
        if event.src_path == self.filepath:
            # Read new lines
            for line in self.file:
                record = self.parser.parse_line(line)
                yield record

    def on_moved(self, event):
        # File rotated
        if follow_name and event.src_path == self.filepath:
            self.file.close()
            # Wait for new file to appear
            while not os.path.exists(self.filepath):
                time.sleep(0.1)
            self.file = open(self.filepath, 'r')
```

### Fallback to Polling

If file is on network filesystem (NFS, SMB) where inotify doesn't work:

```python
def poll_file(filepath, interval=1.0):
    with open(filepath, 'r') as f:
        f.seek(0, os.SEEK_END)

        while True:
            line = f.readline()
            if line:
                yield parse_line(line)
            else:
                time.sleep(interval)
```

## Use Cases

### Real-time Log Monitoring

```bash
# Watch for errors
jn follow /var/log/app.log | jq 'select(.level == "ERROR")' | jn put slack://alerts

# Track API response times
jn follow access.log --parser apache_log_s | \
  jq 'select(.response_time > 1000)' | \
  jn put influxdb://metrics
```

### Continuous Data Ingestion

```bash
# CSV file continuously appended by another process
jn follow data.csv | jq 'select(.amount > 1000)' | jn put postgres://db/high_value

# Real-time metrics
jn follow metrics.json | jn put prometheus://pushgateway
```

### Development Debugging

```bash
# Watch test output
jn follow test-results.json | jq 'select(.status == "failed")'

# Monitor build logs
jn follow build.log --from-start | grep ERROR
```

## Folder Sources (Using JC)

JC already has `ls` and `find` parsers. Use those for folder operations.

### List Files in Folder

```bash
# Using ls parser
jn cat ls ./inbox/

# Output (JC ls parser format)
{"filename": "data.csv", "size": 1024, "date": "Jan 15 10:30", ...}
{"filename": "report.json", "size": 2048, "date": "Jan 15 11:00", ...}
```

### Find Files Recursively

```bash
# Using find parser
jn cat find ./data/ -name "*.csv"

# Output (JC find parser format)
{"path": "./data/sales.csv", "size": 1024, ...}
{"path": "./data/archive/old.csv", "size": 512, ...}
```

### Extract File Paths

```bash
# Get list of files to process
jn cat ls ./inbox/ | jq -r '.filename' | while read file; do
  jn cat "./inbox/$file" | jq '...' | jn put "./output/$file"
done
```

### Filter by File Properties

```bash
# Files larger than 1MB
jn cat ls ./uploads/ | jq 'select(.size > 1048576)'

# Files modified today
jn cat ls ./data/ | jq 'select(.date | startswith("Jan 15"))'
```

## Integration with External Watchers

### Using watchdog CLI

```bash
# Install watchdog
pip install watchdog[watchmedo]

# Watch folder, run pipeline on new files
watchmedo shell-command \
  --patterns="*.csv" \
  --recursive \
  --command='jn run process.json --input-file ${watch_src_path}' \
  ./inbox/
```

### Using systemd Path Units

```ini
# /etc/systemd/system/jn-watcher.path
[Unit]
Description=Watch folder for CSV files

[Path]
PathChanged=/data/inbox

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/jn-watcher.service
[Unit]
Description=Process CSV files

[Service]
Type=oneshot
ExecStart=/usr/local/bin/jn run process.json --input-file %f
```

### Using inotifywait

```bash
#!/bin/bash
inotifywait -m -e create --format '%f' ./inbox/ | while read file; do
  jn run process.json --input-file "./inbox/$file"
done
```

### Using Python watchdog Library

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess

class CSVHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.src_path.endswith('.csv'):
            subprocess.run([
                'jn', 'run', 'process.json',
                '--input-file', event.src_path
            ])

observer = Observer()
observer.schedule(CSVHandler(), path='./inbox/', recursive=False)
observer.start()
```

## Embedding watchdog in JN (Optional)

If we want `jn watch` command later, embed the watchdog library:

```python
# src/jn/cli/watch.py
import typer
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def watch(
    folder: Path,
    pipeline: Path,
    pattern: str = "*.csv",
):
    """Watch folder and run pipeline on new files"""

    class PipelineHandler(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory and fnmatch(event.src_path, pattern):
                # Run pipeline with file as argument
                subprocess.run([
                    'jn', 'run', str(pipeline),
                    '--input-file', event.src_path
                ])

    observer = Observer()
    observer.schedule(PipelineHandler(), str(folder), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
```

**Usage**:
```bash
jn watch ./inbox/ --pipeline process.json --pattern "*.csv"
```

**Decision**: Start without `jn watch`. Let users use external tools. Add `jn watch` later if there's demand.

## Dependencies

```toml
[tool.poetry.dependencies]
watchdog = "^3.0.0"  # For follow command (file monitoring)
```

Watchdog handles:
- Cross-platform file system events (Linux, macOS, Windows)
- File rotation detection
- Polling fallback for network filesystems
- Race condition handling

## Testing Strategy

### Unit Tests
- File following logic
- Parser integration
- Start position (end, beginning, tail N)
- File rotation detection

### Integration Tests
- Follow a file, append lines, verify output
- Follow with auto-detected parser
- Follow with explicit parser
- Handle file rotation
- Handle file deletion and recreation

### Test Helpers

```python
def test_follow_csv(tmp_path):
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("name,age\n")

    # Start following
    follower = follow(csv_file)

    # Append line
    with open(csv_file, 'a') as f:
        f.write("Alice,30\n")

    # Should get new record
    record = next(follower)
    assert record == {"name": "Alice", "age": "30"}
```

## Success Criteria

- [x] Can follow a file and emit new lines
- [x] Auto-detects parser from file extension
- [x] Can start from end (default) or beginning (--from-start)
- [x] Can show last N lines before following (--tail N)
- [x] Handles file rotation (--follow-name)
- [x] Works with streaming parsers (csv_s, json_s, etc.)
- [x] Can pipe to jq and other commands
- [x] Falls back to polling on network filesystems
- [x] Test coverage >80%
- [x] Documentation with examples

## Out of Scope (External Tools Handle This)

- Watching folders for new files → Use watchdog CLI / systemd / inotifywait
- Running pipelines on file events → Use arguments + external watcher
- Daemon mode → Use systemd / supervisord / Docker
- Retry logic → Use external orchestration (Airflow, Prefect)
- State management → Use external database
- Distributed execution → Use external orchestration

**Keep JN focused on data transformation. Let orchestration tools handle orchestration.**
