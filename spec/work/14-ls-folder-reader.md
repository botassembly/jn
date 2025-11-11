# LS Folder Reader Plugin

## What
Read directory contents as NDJSON records. Alternative to JC's ls parser - direct Python implementation.

## Why
Enable folder listings in pipelines without shelling out to ls command. Portable, fast, and doesn't require parsing text output.

## Key Features
- Read directory contents (files, subdirectories)
- File metadata (size, mtime, mode, owner)
- Recursive directory traversal (optional)
- Glob pattern filtering
- Hidden file handling
- Symlink resolution

## Dependencies
- Python stdlib only (`os`, `pathlib`, `stat`)

## Examples
```bash
# List directory
jn cat folder:///home/user | jn filter '.size > 1000000' | jn jtbl

# Recursive listing
jn cat folder:///var/log --recursive | jn filter '.name =~ "\\.log$"' | jn put log-files.csv

# Find large files
jn cat folder:///data --recursive | jn filter '.size > 100000000' | jn put large-files.json

# Group by extension
jn cat folder:///documents | jn filter 'group_by(.extension) | map({ext: .[0].extension, count: length})'
```

## Record Structure
```json
{
  "path": "/home/user/file.txt",
  "name": "file.txt",
  "extension": ".txt",
  "size": 1024,
  "mtime": "2024-01-15T10:30:00Z",
  "mode": "0644",
  "type": "file",
  "is_hidden": false
}
```

## URL Syntax
- `folder:///absolute/path` - List absolute path
- `folder://./relative/path` - List relative path
- `folder:///path?recursive=true` - Recursive traversal
- `folder:///path?pattern=*.py` - Glob filtering

## Out of Scope
- File content reading (use jn cat file://...)
- File operations (move, delete, copy) - use shell
- Detailed ACLs - basic mode only
