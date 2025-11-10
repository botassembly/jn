# Plugin System

## Overview

JN plugins are **standalone Python scripts** that follow stdin → process → stdout pattern. They're discovered via regex (no imports) and can optionally use profiles for configuration.

## Current Plugin Structure

```
plugins/
├── readers/              # Format parsers (csv, json, xlsx, etc.)
├── writers/              # Format generators (csv, json, xlsx, etc.)
├── filters/              # Transformations (jq_filter)
├── http/                 # HTTP transports (s3_get, http_get, ftp_get)
└── shell/                # Shell commands (ls, ps, find, etc.)
```

## Plugin Discovery

**Locations searched (priority order - highest to lowest):**

1. `--home <path>` (CLI flag)
2. `$JN_HOME` (environment variable)
3. `./.jn/plugins/` (project-specific)
4. `~/.local/jn/plugins/` (user home)
5. `<package>/plugins/` (built-in)

**First found wins** - allows CLI/env/project to override user/built-in plugins.

**Discovery method:** Regex parsing of file contents
- No Python imports needed
- Fast (~10ms for 20+ plugins)
- Extracts META headers, PEP 723 deps

## Plugin Interface

```python
#!/usr/bin/env python3
# /// script
# dependencies = ["library>=1.0.0"]  # PEP 723
# ///
# META: type=source, handles=[".csv"]
# KEYWORDS: csv, data, parsing
# DESCRIPTION: Read CSV files and output NDJSON

def run(config: dict) -> Iterator[dict]:
    """Main entry point. Yields NDJSON records."""
    for line in sys.stdin:
        yield process(line)

def schema() -> dict:
    """Return JSON schema for output (optional)."""
    return {"type": "object"}

def test() -> bool:
    """Run outside-in tests (optional)."""
    pass
```

## Plugin Types

**Sources** - Read data → output NDJSON
- Readers: Parse formats (csv_reader, xlsx_reader, json_reader, etc.)
- HTTP: Fetch from URLs (s3_get, http_get, ftp_get)
- Shell: Execute commands (ls, ps, find, etc.)

**Filters** - Transform NDJSON → NDJSON
- jq_filter: JSON filtering/transformation

**Targets** - Read NDJSON → write output
- Writers: Generate formats (csv_writer, json_writer, xlsx_writer, etc.)

## Extension-Based Routing

The registry maps file extensions to plugins:
- `.csv` → `csv_reader`
- `.json` → `json_reader`
- `.xlsx` → `xlsx_reader`

**Example:**
```bash
jn cat data.xlsx  # Auto-detects .xlsx → uses xlsx_reader
```

## URL-Based Routing

The registry maps URL schemes to plugins:
- `s3://` → `s3_get`
- `ftp://` → `ftp_get`
- `http://`, `https://` → `http_get`

**Example:**
```bash
jn cat s3://bucket/file.xlsx  # s3:// → s3_get → xlsx_reader
jn cat https://api.github.com/repos/org/repo/issues  # http_get
```

## Custom Plugin Development

Create a new plugin in user's JN_HOME:

```python
# ~/.local/jn/plugins/readers/parquet_reader.py
#!/usr/bin/env python3
# /// script
# dependencies = ["pyarrow>=10.0.0"]
# ///
# META: type=source, handles=[".parquet"]

def run(config):
    """Read Parquet file, yield NDJSON."""
    import pyarrow.parquet as pq

    filepath = config.get('filepath') or config.get('url')
    table = pq.read_table(filepath)

    for batch in table.to_batches():
        for row in batch.to_pylist():
            yield row
```

**Auto-discovered and used:**
```bash
jn cat data.parquet  # Automatically uses parquet_reader
```

## Profile System (Planned v4.2.0)

**Design goal:** Support profile-based configuration for APIs, databases, and MCP servers.

**Planned usage:**
```bash
# With profile
jn cat @github/repos/anthropics/claude-code/issues

# Direct URL (still works)
jn cat https://api.github.com/repos/anthropics/claude-code/issues
```

See `arch/profiles.md` for complete profile system design.

## Key Principles

- **Standalone scripts** - Can run without framework
- **Regex discovery** - No imports, fast scanning
- **Priority-based** - CLI > env > project > user > built-in
- **Self-documenting** - META headers, inline tests
- **Language-agnostic** - Any language that uses stdin/stdout
- **Zero coupling** - Plugins don't know about each other

See also:
- `arch/backpressure.md` - Streaming details
- `arch/pipeline.md` - Pipeline execution
- `arch/profiles.md` - Profile system design (planned)
