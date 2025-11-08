# Streaming and Watching: Continuous ETL Architecture

## Overview

Extension of JN to support continuous, event-driven ETL workflows. This moves JN from "run once" pipelines to "always running" background processes that monitor file systems, process data as it arrives, and chain together complex multi-stage workflows.

## Core Concepts

### 1. Folders as Sources/Targets

Folders become first-class citizens alongside files.

### 2. Follow/Watch

Continuous monitoring of files and folders for changes.

### 3. Pipeline Arguments

Parameterized pipelines that accept runtime arguments instead of hardcoded paths.

### 4. Event-Driven Execution

Trigger pipelines automatically when file system events occur.

### 5. Folder Ecosystems

Chain multiple folders together where one folder's output feeds another's input.

## 1. Folders as Sources

### Folder Source: File Metadata

When you `cat` a folder, emit records about files in that folder (not file contents).

**Record structure**:
```json
{
  "_kind": "file",
  "path": "./inbox/data.csv",
  "name": "data.csv",
  "extension": ".csv",
  "size": 1024,
  "modified": "2025-01-15T10:30:00Z",
  "created": "2025-01-15T09:00:00Z"
}
```

### CLI Usage

```bash
# List all files in folder
jn cat ./inbox/

# With options
jn cat ./inbox/ \
  --recursive \              # Include subdirectories
  --pattern '*.csv' \        # Filter by glob pattern
  --sort modified \          # Sort by: name, modified, created, size
  --reverse                  # Reverse sort order

# Get just file paths
jn cat ./inbox/ | jq -r '.path'

# Filter by extension
jn cat ./inbox/ | jq 'select(.extension == ".csv")'

# Files modified in last hour
jn cat ./inbox/ | jq 'select(.modified > (now - 3600))'
```

### Advanced: Include File Contents

```bash
# Emit file metadata AND contents
jn cat ./inbox/ --contents

# Each file becomes multiple records:
# 1. File metadata record
# 2. Content records (parsed according to file type)
```

Output:
```json
{"_kind": "file", "path": "./inbox/users.csv", "name": "users.csv", "size": 256}
{"_kind": "csv_row", "source": "./inbox/users.csv", "Name": "Alice", "Age": 30}
{"_kind": "csv_row", "source": "./inbox/users.csv", "Name": "Bob", "Age": 25}
{"_kind": "file", "path": "./inbox/sales.json", "name": "sales.json", "size": 512}
{"_kind": "json_object", "source": "./inbox/sales.json", "product": "Widget", "revenue": 1000}
```

### Use Cases

**Process all CSV files in a folder**:
```bash
jn cat ./inbox/ --pattern '*.csv' | \
  jq -r '.path' | \
  xargs -I {} jn cat {} | \
  jq 'select(.amount > 1000)' | \
  jn put ./output/high-value.csv
```

**Find largest files**:
```bash
jn cat ./data/ --recursive | jq 'select(.size > 1000000)' | jq -r '.path'
```

**Backup old files**:
```bash
jn cat ./active/ | \
  jq 'select(.modified < (now - 86400*30))' | \
  jq -r '.path' | \
  xargs -I {} mv {} ./archive/
```

## 2. Folders as Targets

### Two Modes

#### Mode A: Explicit Filenames (Record-Driven)

Each NDJSON record specifies a filename and content.

**Record structure**:
```json
{"filename": "user-001.json", "content": "{\"name\": \"Alice\", \"age\": 30}"}
{"filename": "user-002.json", "content": "{\"name\": \"Bob\", \"age\": 25}"}
```

**Usage**:
```bash
jn cat users.csv | \
  jq '{filename: (.id + ".json"), content: tojson}' | \
  jn put ./output/
```

Creates:
```
./output/user-001.json
./output/user-002.json
```

#### Mode B: Automatic Splitting (Split-By Strategy)

Split NDJSON stream into multiple files based on a field value.

**Usage**:
```bash
jn cat products.csv | jn put ./output/ --split-by category --format json
```

If products have categories: electronics, books, toys

Creates:
```
./output/electronics.json
./output/books.json
./output/toys.json
```

Each file contains NDJSON records for that category.

**Advanced splitting**:
```bash
# Split by date
jn cat events.json | jn put ./daily/ --split-by date --format csv

# Creates ./daily/2025-01-15.csv, ./daily/2025-01-16.csv, etc.

# Split by size (create new file every 1000 records)
jn cat large.csv | jn put ./chunks/ --split-size 1000 --format json

# Creates ./chunks/chunk-001.json, ./chunks/chunk-002.json, etc.
```

### Edge Cases

**Filename conflicts**:
- Default: error if file exists
- `--overwrite`: replace existing
- `--append`: append to existing
- `--skip`: skip if exists

**Directory creation**:
- Auto-create parent directories if they don't exist
- Or error with `--no-create-dirs`

**Invalid filenames**:
- Sanitize (remove `/`, `\`, `:`, etc.)
- Or error with `--strict`

## 3. Follow Command

Continuous monitoring, like `tail -F` but for files and folders.

### Follow a File

Watch file and emit new lines as they're appended.

```bash
# Basic follow
jn follow access.log

# With parser
jn follow access.log --parser apache_log

# Follow and filter
jn follow access.log | jq 'select(.status >= 500)'

# Follow and alert
jn follow access.log | jq 'select(.status >= 500)' | jn put slack://alerts
```

**Behavior**:
- Starts at end of file (like `tail -f`)
- Use `--from-start` to read entire file first
- Continues even if file is rotated (like `tail -F`)
- Auto-detects parser from extension

### Follow a Folder

Watch folder and emit events when files are created/modified/deleted.

```bash
# Basic folder watching
jn follow ./inbox/

# With filtering
jn follow ./inbox/ --pattern '*.csv'

# Only certain events
jn follow ./inbox/ --events created,modified
```

**Event record structure**:
```json
{
  "_kind": "fs_event",
  "event": "created",
  "path": "./inbox/data.csv",
  "name": "data.csv",
  "size": 1024,
  "timestamp": "2025-01-15T10:30:00Z"
}
```

**Event types**:
- `created`: New file added
- `modified`: File content changed
- `deleted`: File removed
- `moved`: File renamed/moved

### Use Cases

**Process files as they arrive**:
```bash
jn follow ./inbox/ --events created | \
  jq -r '.path' | \
  xargs -I {} jn cat {} | \
  jn put ./output/processed.json
```

**Alert on large files**:
```bash
jn follow ./uploads/ --events created | \
  jq 'select(.size > 10000000)' | \
  jq '{text: "Large file uploaded: \(.name)"}' | \
  jn put slack://monitoring
```

**Real-time log aggregation**:
```bash
jn follow /var/log/app.log | \
  jq 'select(.level == "ERROR")' | \
  jn put elasticsearch://logs/errors
```

## 4. Pipeline Arguments

### Current Problem

Pipelines today have hardcoded paths:

```yaml
# pipeline.yml
source:
  driver: file
  path: data.csv  # HARDCODED!
  parser: csv
```

This means you need a separate config for each input file. Not scalable.

### Solution: Parameterized Pipelines

**Declare arguments** in pipeline config:

```yaml
# process-csv.yml
arguments:
  input_file:
    type: path
    required: true
    description: "Path to input CSV file"

  min_amount:
    type: number
    default: 100
    description: "Minimum amount to filter"

  output_format:
    type: string
    default: json
    enum: [json, csv, excel]

source:
  driver: file
  path: ${input_file}
  parser: csv

converter:
  query: 'select(.amount >= ${min_amount})'

target:
  driver: file
  path: output.${output_format}
  format: ${output_format}
```

**Run with arguments**:
```bash
jn run process-csv.yml \
  --input-file data/sales.csv \
  --min-amount 500 \
  --output-format excel
```

### Argument Types

- `path`: File or folder path (validates existence)
- `string`: Text value
- `number`: Integer or float
- `boolean`: true/false
- `enum`: Limited set of choices

### Variable Substitution

Use `${variable_name}` anywhere in the config:

```yaml
source:
  driver: file
  path: ${input_folder}/${input_file}
  parser: ${input_format}

converter:
  query: 'select(.${filter_field} >= ${filter_value})'

target:
  driver: ${output_driver}
  path: ${output_path}
```

### Default Values and Validation

```yaml
arguments:
  input_file:
    type: path
    required: true
    exists: true  # Validate file exists before running

  threshold:
    type: number
    default: 100
    min: 0
    max: 1000

  mode:
    type: string
    default: append
    enum: [append, overwrite, skip]
```

Validation happens BEFORE pipeline runs, with clear error messages.

### Stdin as Arguments

Can also pass arguments via stdin:

```bash
# Generate arguments with jq
jq -n '{input_file: "data.csv", threshold: 500}' | jn run pipeline.yml --args-stdin

# From another pipeline
jn cat ./inbox/ | \
  jq '{input_file: .path, threshold: 500}' | \
  jn run pipeline.yml --args-stdin --each
```

The `--each` flag runs the pipeline once per input record.

## 5. Watch Command (Event-Driven Pipelines)

Combining folders, follow, and arguments into automated workflows.

### Simple Watch

```bash
# Watch folder, run pipeline on each new file
jn watch ./inbox/ --run process.yml --arg input_file={path}

# Watch with pattern matching
jn watch ./inbox/ --pattern '*.csv' --run process-csv.yml --arg input_file={path}

# Watch and execute shell command
jn watch ./inbox/ --exec 'jn cat {path} | jq "." | jn put ./output/{name}.json'
```

**Placeholder variables**:
- `{path}`: Full path to file
- `{name}`: Filename only
- `{dir}`: Directory path
- `{ext}`: Extension

### Watch Config File

For complex scenarios, use a config file:

```yaml
# watch.yml
watch:
  path: ./inbox/
  pattern: "*.csv"
  recursive: false
  events: [created]

  # Optional: debounce rapid events
  debounce: 1s

on_event:
  # Run pipeline with arguments from event
  pipeline: process.yml
  arguments:
    input_file: ${event.path}
    input_name: ${event.name}
    input_size: ${event.size}

  # Actions on success
  on_success:
    - action: move
      from: ${event.path}
      to: ./processed/${event.name}

    - action: log
      message: "✓ Processed ${event.name}"

  # Actions on error
  on_error:
    - action: move
      from: ${event.path}
      to: ./failed/${event.name}

    - action: log
      level: error
      message: "✗ Failed to process ${event.name}: ${error.message}"

    - action: notify
      url: slack://errors
      message: "Pipeline failed for ${event.name}"
```

**Run the watcher**:
```bash
jn watch watch.yml
```

### Available Actions

**move**: Move file after processing
```yaml
- action: move
  from: ${event.path}
  to: ./archive/${event.name}
```

**copy**: Copy file after processing
```yaml
- action: copy
  from: ${event.path}
  to: ./backup/${event.name}
```

**delete**: Delete file after processing
```yaml
- action: delete
  path: ${event.path}
```

**log**: Write to log
```yaml
- action: log
  level: info  # debug, info, warning, error
  message: "Processed ${event.name}"
```

**notify**: Send notification
```yaml
- action: notify
  url: slack://monitoring
  message: "File processed: ${event.name}"
```

**exec**: Run shell command
```yaml
- action: exec
  command: "aws s3 cp ${event.path} s3://bucket/data/"
```

### Multiple Watchers

Watch multiple folders in one config:

```yaml
watchers:
  - name: csv-ingest
    path: ./inbox/csv/
    pattern: "*.csv"
    pipeline: process-csv.yml
    on_success:
      - action: move
        to: ./processed/

  - name: json-ingest
    path: ./inbox/json/
    pattern: "*.json"
    pipeline: process-json.yml
    on_success:
      - action: move
        to: ./processed/

  - name: error-handler
    path: ./failed/
    events: [created]
    on_event:
      - action: notify
        url: slack://errors
```

## 6. Folder Ecosystems (Chaining)

Multiple folders feeding into each other.

### Example: Three-Stage Pipeline

```
inbox/     →  [ingest]     →  staging/
staging/   →  [transform]  →  ready/
ready/     →  [export]     →  uploaded/ + external API
errors/    ←  [any stage fails]
```

**Config**:
```yaml
watchers:
  - name: stage1-ingest
    path: ./inbox/
    pattern: "*.csv"
    events: [created]
    pipeline: ingest.yml
    arguments:
      input_file: ${event.path}
    on_success:
      - action: move
        to: ./staging/${event.name}.json
    on_error:
      - action: move
        to: ./errors/stage1-${event.name}

  - name: stage2-transform
    path: ./staging/
    pattern: "*.json"
    events: [created]
    pipeline: transform.yml
    arguments:
      input_file: ${event.path}
    on_success:
      - action: move
        to: ./ready/${event.name}
    on_error:
      - action: move
        to: ./errors/stage2-${event.name}

  - name: stage3-export
    path: ./ready/
    pattern: "*.json"
    events: [created]
    pipeline: export.yml
    arguments:
      input_file: ${event.path}
    on_success:
      - action: move
        to: ./uploaded/${event.name}
      - action: log
        message: "✓ Complete pipeline for ${event.name}"
    on_error:
      - action: move
        to: ./errors/stage3-${event.name}
```

### Use Cases

**Data ingestion pipeline**:
```
raw-uploads/  →  [parse & validate]    →  validated/
validated/    →  [enrich & transform]  →  enriched/
enriched/     →  [load to database]    →  loaded/
```

**Document processing**:
```
inbox/        →  [OCR + extract]       →  extracted/
extracted/    →  [classify]            →  classified/
classified/   →  [route by type]       →  invoices/ | receipts/ | other/
```

**ETL with retries**:
```
inbox/        →  [try process]         →  success/ or retry/
retry/        →  [wait 5min, retry]    →  success/ or dead-letter/
```

## 7. Daemon Mode

Run watchers as background processes.

### Commands

```bash
# Start a daemon
jn daemon start watch.yml --name my-watcher

# List running daemons
jn daemon list

# Check status
jn daemon status my-watcher

# View logs (real-time)
jn daemon logs my-watcher --follow

# View logs (last N lines)
jn daemon logs my-watcher --tail 100

# Stop daemon
jn daemon stop my-watcher

# Restart daemon
jn daemon restart my-watcher

# Stop all daemons
jn daemon stop --all
```

### Daemon Output

```bash
$ jn daemon list

NAME          STATUS    UPTIME    PROCESSED    ERRORS    CPU%    MEM
my-watcher    running   2d 5h     1,234        3         0.5%    45MB
csv-monitor   running   1h 23m    45           0         0.2%    32MB
```

### Logging

Logs stored in `~/.jn/logs/`:
```
~/.jn/logs/
  my-watcher.log
  my-watcher.error.log
```

**Log format**:
```
2025-01-15 10:30:00 [INFO] Watcher started: ./inbox/
2025-01-15 10:30:15 [INFO] File created: data.csv
2025-01-15 10:30:16 [INFO] Running pipeline: process.yml
2025-01-15 10:30:18 [INFO] ✓ Processed data.csv
2025-01-15 10:30:18 [INFO] Moved to ./processed/data.csv
```

### Process Management

Uses standard Unix process management:
- PID files in `~/.jn/run/`
- Signal handling (SIGTERM for graceful shutdown)
- Auto-restart on crash (optional with `--restart`)

## Implementation Strategy

### Phase 1: Folder Sources (1-2 days)
- Implement folder adapter that emits file metadata records
- Add CLI options: --recursive, --pattern, --sort
- Add --contents flag for including file data
- Integration tests

### Phase 2: Folder Targets (1-2 days)
- Implement folder writer with explicit filenames
- Add --split-by for automatic splitting
- Handle edge cases (conflicts, sanitization)
- Integration tests

### Phase 3: Follow Command (2-3 days)
- Implement file following (tail -f behavior)
- Implement folder watching using watchdog library
- Add event filtering and pattern matching
- Handle file rotation
- Integration tests

### Phase 4: Pipeline Arguments (2-3 days)
- Add argument declaration to pipeline config schema
- Implement variable substitution engine
- Add validation (types, ranges, existence)
- Add CLI flags for passing arguments
- Update pipeline runner
- Tests

### Phase 5: Watch Command (3-4 days)
- Implement simple watch with --run and --exec
- Implement watch config file format
- Add on_success/on_error actions
- Add debouncing
- Integration tests with temp directories

### Phase 6: Daemon Mode (3-4 days)
- Implement process daemonization
- Add PID file management
- Add logging infrastructure
- Add status monitoring
- Add CLI commands (start, stop, list, logs)
- Tests

### Total: 12-18 days

## Dependencies

```toml
[tool.poetry.dependencies]
watchdog = "^3.0.0"    # File system event monitoring
python-daemon = "^3.0.0"  # Daemonization
psutil = "^5.9.0"      # Process management and monitoring
```

## Configuration Examples

### Simple CSV Processing Pipeline

```yaml
# csv-to-json.yml
arguments:
  input_file:
    type: path
    required: true

source:
  driver: file
  path: ${input_file}
  parser: csv

converter:
  query: 'select(.amount > 100)'

target:
  driver: file
  path: output.json
  format: json
```

Watch folder and process:
```bash
jn watch ./inbox/ --pattern '*.csv' --run csv-to-json.yml --arg input_file={path}
```

### Multi-Stage Folder Ecosystem

```yaml
# ecosystem.yml
watchers:
  - name: ingest
    path: ./inbox/
    pattern: "*.csv"
    pipeline: ingest.yml
    arguments:
      input: ${event.path}
    on_success:
      - action: move
        to: ./staging/${event.name}.json
    on_error:
      - action: move
        to: ./errors/

  - name: transform
    path: ./staging/
    pattern: "*.json"
    pipeline: transform.yml
    arguments:
      input: ${event.path}
    on_success:
      - action: move
        to: ./output/${event.name}
```

Run as daemon:
```bash
jn daemon start ecosystem.yml --name data-pipeline
```

### Real-Time Log Processing

```yaml
# log-monitoring.yml
watch:
  path: /var/log/app.log
  type: file  # Watch single file, not folder

on_line:
  converter:
    parser: json
    query: 'select(.level == "ERROR")'

  target:
    driver: http
    url: https://api.monitoring.com/events
    method: POST
```

Run:
```bash
jn watch log-monitoring.yml
```

## Security Considerations

**Folder access**:
- Validate folder paths (no path traversal)
- Check permissions before watching
- Limit recursive depth (prevent symlink loops)

**Daemon isolation**:
- Run daemons as unprivileged user
- Limit resource usage (CPU, memory, disk)
- Rate limiting for event processing

**Argument injection**:
- Sanitize arguments before substitution
- No shell execution in variable expansion
- Validate paths strictly

**Action safety**:
- Confirm before destructive actions (delete, move)
- Atomic file operations
- Transaction-like semantics (rollback on error)

## Success Criteria

- [x] Can list files in a folder as NDJSON records
- [x] Can write NDJSON stream to multiple files in a folder
- [x] Can follow a file (tail -f) and emit new lines
- [x] Can watch a folder and emit file system events
- [x] Can declare and use arguments in pipelines
- [x] Can trigger pipelines from file system events
- [x] Can move/delete files after successful processing
- [x] Can chain multiple folders together
- [x] Can run watchers as background daemons
- [x] Can monitor daemon status and view logs
- [x] All features work with cat/head/tail/put/follow
- [x] Test coverage >80%
- [x] Documentation with examples
