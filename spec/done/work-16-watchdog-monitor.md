# Watchdog File Monitor Plugin

## What
Monitor file system events (create, modify, delete, move) using watchdog library. Stream events as NDJSON.

## Why
React to file system changes in real-time. Enable automated workflows triggered by file changes.

## Key Features
- Monitor directories for file events (created, modified, deleted, moved)
- Recursive directory watching
- Pattern filtering (glob/regex)
- Event debouncing (avoid duplicate events)
- Cross-platform (Linux inotify, macOS FSEvents, Windows)

## Dependencies
- `watchdog` (Python file system monitoring library)

## Examples
```bash
# Watch directory for changes
jn watch /data/incoming | jn filter '.event_type == "created"' | jn put new-files.json

# Monitor and process new files
jn watch /uploads --pattern "*.csv" | jn filter '.event_type == "created"' |
  xargs -I {} jn cat {} | jn filter '.amount > 1000' | jn put processed.json

# Detect modifications
jn watch /config --pattern "*.toml" | jn filter '.event_type == "modified"' | jn put config-changes.log

# Multiple directories
jn watch /logs /data --recursive | jn filter '.path =~ "\\.log$"' | jn jtbl
```

## Record Structure
```json
{
  "event_type": "created",
  "path": "/data/incoming/file.csv",
  "is_directory": false,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

For move events:
```json
{
  "event_type": "moved",
  "src_path": "/data/old.csv",
  "dest_path": "/data/new.csv",
  "is_directory": false,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Event Types
- `created` - New file/directory created
- `modified` - File/directory modified
- `deleted` - File/directory deleted
- `moved` - File/directory moved/renamed

## URL Syntax
- `watch:///data/incoming` - Watch directory
- `watch:///data?recursive=true` - Watch recursively
- `watch:///data?pattern=*.csv` - Filter by pattern
- `watch:///data?debounce=1.0` - Debounce events (1 second)

## Out of Scope
- File content processing (use jn cat after detecting change)
- Complex event filtering logic (use jn filter)
- Historical events (only real-time monitoring)
