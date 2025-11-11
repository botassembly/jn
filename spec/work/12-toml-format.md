# TOML Format Plugin

## What
Read and write TOML configuration files (.toml), convert to/from NDJSON.

## Why
TOML is the standard for Python configs (pyproject.toml, PEP 723), Rust (Cargo.toml), and many tools. Enable processing config files in pipelines.

## Key Features
- Read TOML files to NDJSON
- Write NDJSON to TOML format
- Preserve data types (strings, numbers, dates, arrays, tables)
- Handle nested tables and array-of-tables
- Support TOML 1.0 spec

## Dependencies
- `tomli` (read TOML, built into Python 3.11+)
- `tomli-w` (write TOML)

## Examples
```bash
# Read config file
jn cat pyproject.toml | jn filter '.tool.jn.dependencies' | jn jtbl

# Extract all dependencies from multiple projects
jn cat */pyproject.toml | jn filter '.project.dependencies[]' | jn put all-deps.csv

# Convert TOML to JSON
jn cat config.toml | jn put config.json

# Convert JSON to TOML
jn cat settings.json | jn put config.toml

# Merge configs
jn cat base.toml extra.toml | jn filter 'reduce . as $item ({}; . * $item)' | jn put merged.toml
```

## TOML Structure
Convert TOML sections to nested objects:
```toml
[tool.jn]
version = "1.0"
dependencies = ["click", "requests"]
```

Becomes:
```json
{"tool": {"jn": {"version": "1.0", "dependencies": ["click", "requests"]}}}
```

## Out of Scope
- TOML validation/linting - use dedicated tools
- Comments preservation (TOML parsers strip comments)
