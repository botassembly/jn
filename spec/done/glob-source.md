# Glob-Based Source for Nested Folder Structures

**Status:** Implemented
**Version:** 1.0
**Last Updated:** 2025-11-28

## Overview

JN now supports glob-based sources that can read multiple files from nested directory structures, with automatic format detection and path metadata injection. This enables powerful analytics across files organized by folder, status, or any hierarchical structure.

## Key Features

### 1. Glob Pattern Recognition

JN automatically recognizes glob patterns and routes them to the glob plugin:

```bash
# Recursive pattern - read all JSONL files under processes/
jn cat "processes/**/*.jsonl"

# Simple wildcard - read all JSON files in current directory
jn cat "*.json"

# Character class - read files matching pattern
jn cat "data[0-9].csv"

# Explicit glob protocol
jn cat "glob://data/**/*.jsonl"
```

### 2. Path Metadata Injection

Every record from a glob source includes metadata about its origin:

| Field | Description | Example |
|-------|-------------|---------|
| `_path` | Relative path to file | `"processes/failed/abc.jsonl"` |
| `_dir` | Directory containing file | `"processes/failed"` |
| `_filename` | Filename with extension | `"abc.jsonl"` |
| `_basename` | Filename without extension | `"abc"` |
| `_ext` | File extension (with dot) | `".jsonl"` |
| `_file_index` | 0-based index of file in glob results | `0` |
| `_line_index` | 0-based index of record within file | `5` |

Example output:
```json
{
  "_path": "processes/failed/550e8400.jsonl",
  "_dir": "processes/failed",
  "_filename": "550e8400.jsonl",
  "_basename": "550e8400",
  "_ext": ".jsonl",
  "_file_index": 0,
  "_line_index": 0,
  "workflow_run_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "process.start",
  ...
}
```

### 3. Multi-Format Support

Each file in a glob pattern is parsed according to its extension:

```bash
# Mix of JSONL and CSV files
jn cat "data/**/*.{jsonl,csv}"  # Note: brace expansion not supported
jn cat "data/**/*.jsonl"         # Read all JSONL
jn cat "data/**/*.csv"           # Read all CSV

# Each file uses appropriate parser:
# - .jsonl, .ndjson, .json → JSON plugin
# - .csv, .tsv → CSV plugin
# - .yaml, .yml → YAML plugin
# - etc.
```

### 4. Push-Down Filtering

Use jq to filter based on path components:

```bash
# Filter to specific directory
jn cat "processes/**/*.jsonl" | jn filter 'select(._dir | contains("failed"))'

# Filter by filename pattern
jn cat "processes/**/*.jsonl" | jn filter 'select(._basename | startswith("550e"))'

# Filter by extension
jn cat "data/**/*" | jn filter 'select(._ext == ".jsonl")'

# Combine path filter with data filter
jn cat "processes/**/*.jsonl" | jn filter 'select(._dir | contains("completed")) | select(.event_type == "ValidationErrorEvent")'
```

### 5. Limit Parameters

Control the amount of data read:

```bash
# Limit total records
jn cat "processes/**/*.jsonl?limit=100"

# Limit number of files processed
jn cat "processes/**/*.jsonl?file_limit=10"

# Both together
jn cat "processes/**/*.jsonl?limit=1000&file_limit=50"
```

---

## BotAssembly Integration Guide

### Recommended Directory Structure

Based on the BotAssembly JSONL Analytics Toolkit specification:

```
$BOTASSEMBLY_HOME/
├── processes/
│   ├── active/                  # Currently running
│   │   └── {uuid}.jsonl
│   ├── completed/               # Successfully finished
│   │   └── {uuid}.jsonl
│   └── failed/                  # Crashed or errored
│       └── {uuid}.jsonl
```

### Basic Usage Patterns

```bash
# Read all process events
jn cat "$BOTASSEMBLY_HOME/processes/**/*.jsonl"

# Read only failed processes
jn cat "$BOTASSEMBLY_HOME/processes/failed/*.jsonl"

# Read with status awareness (using _dir)
jn cat "$BOTASSEMBLY_HOME/processes/**/*.jsonl" | \
  jn filter 'select(._dir | contains("failed"))'
```

### Mapping Metadata to Status

The `_dir` field captures the folder structure. For BotAssembly:

```bash
# Create status field from directory
jn cat "$BOTASSEMBLY_HOME/processes/**/*.jsonl" | \
  jn filter '. + {_status: (._dir | split("/") | .[-1])}'
```

This adds `"_status": "failed"`, `"_status": "completed"`, or `"_status": "active"` to each record.

### Common Analytics Queries

#### 1. Process Discovery

```bash
# List all processes with status
jn cat "$BOTASSEMBLY_HOME/processes/**/*.jsonl" | \
  jn filter 'select(.event_type == "process.start")' | \
  jn filter '{
    process_id: ._basename,
    status: (._dir | split("/") | .[-1]),
    workflow: .payload.workflow_name,
    started: .timestamp
  }'
```

#### 2. Find Failures

```bash
# All validation errors
jn cat "$BOTASSEMBLY_HOME/processes/**/*.jsonl" | \
  jn filter 'select(.event_type == "ValidationErrorEvent")' | \
  jn filter '{
    process: ._basename,
    status: (._dir | split("/") | .[-1]),
    step: .step_id,
    error: .payload.error
  }'
```

#### 3. Aggregate by Status

```bash
# Count records per status
jn cat "$BOTASSEMBLY_HOME/processes/**/*.jsonl" | \
  jn filter '. + {_status: (._dir | split("/") | .[-1])}' | \
  jn filter -s 'group_by(._status) | map({status: .[0]._status, count: length})'
```

#### 4. State Timeline

```bash
# Track state mutations for a process
jn cat "$BOTASSEMBLY_HOME/processes/**/*.jsonl" | \
  jn filter 'select(._basename == "550e8400")' | \
  jn filter 'select(.event_type == "state_mutation")' | \
  jn filter '{seq: .seq, step: .step_id, diff: .payload.diff}'
```

#### 5. Recent Failures

```bash
# Last 10 failed processes' error events
jn cat "$BOTASSEMBLY_HOME/processes/failed/*.jsonl?file_limit=10" | \
  jn filter 'select(.event_type | contains("Error") or .event_type == "process.finish")'
```

### Profile Configuration (Optional)

If you want shorter commands, create a JN profile:

**`~/.jn/profiles/botassembly/_meta.json`:**
```json
{
  "type": "glob",
  "base_path": "${BOTASSEMBLY_HOME}/processes"
}
```

**`~/.jn/profiles/botassembly/all.json`:**
```json
{
  "pattern": "**/*.jsonl",
  "description": "All process events"
}
```

**`~/.jn/profiles/botassembly/failed.json`:**
```json
{
  "pattern": "failed/*.jsonl",
  "description": "Failed process events"
}
```

Then use:
```bash
jn cat @botassembly/all
jn cat @botassembly/failed
```

*Note: Profile support for glob sources is planned but not yet implemented.*

---

## Technical Details

### Address Type Detection

Glob patterns are detected by the presence of these characters:
- `*` - wildcard
- `**` - recursive match
- `[` `]` - character class
- `{` `}` - brace expansion (note: Python glob doesn't support this)

The `?` character is ambiguous with query strings and not used for detection.

### Execution Flow

1. Parser detects glob pattern → sets `address.type = "glob"`
2. Resolver finds glob_ plugin
3. Cat command passes glob pattern to plugin
4. Plugin expands glob, iterates files
5. Each file parsed by appropriate format plugin
6. Path metadata injected into each record
7. Records streamed to stdout

### Memory Characteristics

- **Constant memory:** Files processed one at a time, records streamed
- **Early termination:** `limit` and `file_limit` stop processing early
- **No buffering:** Output starts immediately

### Plugin Location

The glob plugin is located at:
```
jn_home/plugins/protocols/glob_.py
```

---

## API Reference

### Command Syntax

```
jn cat "<glob_pattern>[?parameters]"
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | unlimited | Maximum records to output |
| `file_limit` | int | unlimited | Maximum files to process |
| `hidden` | bool | false | Include hidden files/directories |
| `root` | path | current dir | Base directory for glob |

### Output Schema

Every record includes these fields in addition to the original data:

```typescript
interface GlobMetadata {
  _path: string;       // Relative path to file
  _dir: string;        // Directory part
  _filename: string;   // Filename with extension
  _basename: string;   // Filename without extension
  _ext: string;        // File extension (with dot)
  _file_index: number; // File index in glob results
  _line_index: number; // Record index within file
}
```

---

## Examples

### Example 1: Process Summary Report

```bash
#!/bin/bash
# Generate summary of all processes

jn cat "$BOTASSEMBLY_HOME/processes/**/*.jsonl" | \
  jn filter 'select(.event_type == "process.start" or .event_type == "process.finish")' | \
  jn filter -s '
    group_by(._basename) |
    map({
      process_id: .[0]._basename,
      status: (.[0]._dir | split("/") | .[-1]),
      workflow: (map(select(.event_type == "process.start")) | .[0].payload.workflow_name // "unknown"),
      exit_code: (map(select(.event_type == "process.finish")) | .[0].payload.exit_code // null),
      events: length
    })
  ' | jn table
```

### Example 2: Error Analysis

```bash
#!/bin/bash
# Find common errors across all failed processes

jn cat "$BOTASSEMBLY_HOME/processes/failed/*.jsonl" | \
  jn filter 'select(.event_type == "ValidationErrorEvent")' | \
  jn filter -s '
    group_by(.payload.error) |
    map({error: .[0].payload.error, count: length}) |
    sort_by(.count) |
    reverse |
    .[0:10]
  '
```

### Example 3: Visidata Integration

```bash
# Interactive analysis with Visidata
jn cat "$BOTASSEMBLY_HOME/processes/**/*.jsonl" | \
  jn filter '. + {_status: (._dir | split("/") | .[-1])}' | \
  jn vd
```

---

## Limitations

1. **Brace expansion not supported:** Use multiple globs or `find` instead of `{a,b}`
2. **No real-time monitoring:** Use `jn cat ... | tail -f` for basic watching
3. **No aggregation mode:** Use jq `-s` for summarization
4. **Profile support pending:** Direct glob patterns work; profile shortcuts coming

---

## See Also

- `spec/done/addressability.md` - Universal addressing syntax
- `spec/done/plugin-specification.md` - Plugin development guide
- `src/jn/addressing/parser.py` - Address parsing implementation
- `jn_home/plugins/protocols/glob_.py` - Glob plugin source
