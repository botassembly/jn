# Plugin System

## Overview

JN plugins are **standalone Python scripts** that follow stdin → process → stdout pattern. They're discovered via regex (no imports) and can optionally use profiles for configuration.

## Current Plugin Structure

```
plugins/
├── readers/              # Format parsers (csv, json, xlsx, etc.)
├── writers/              # Format generators (csv, json, xlsx, etc.)
├── filters/              # Transformations (jq, etc.)
├── http/                 # HTTP transports (s3_get, http_get, ftp_get)
└── shell/                # Shell commands (ls, ps, find, etc.)
```

## Plugin Discovery

**Locations searched (priority order):**
1. `~/.local/jn/plugins/` (or custom JN_HOME)
2. `./.jn/plugins/` (project-specific)
3. `<package>/plugins/` (built-in)

**Discovery method:** Regex parsing of file contents
- No Python imports needed
- Fast (~10ms for 20+ plugins)
- Extracts META headers, PEP 723 deps

## Plugin META Headers

```python
#!/usr/bin/env python3
# /// script
# dependencies = ["library>=1.0.0"]  # PEP 723
# ///
# META: type=source, handles=[".csv"]
# KEYWORDS: csv, data, parsing
# DESCRIPTION: Read CSV files and output NDJSON

def run(config):
    """Main entry point. Yields NDJSON records."""
    ...
```

## Plugin Types

**Sources** - Read data → output NDJSON
- Readers: Parse formats (csv_reader, xlsx_reader)
- HTTP: Fetch from URLs (http_get, s3_get, ftp_get)
- Shell: Execute commands (ls, ps, find)

**Filters** - Transform NDJSON → NDJSON
- jq: JSON filtering/transformation

**Targets** - Read NDJSON → write output
- Writers: Generate formats (csv_writer, json_writer)

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

## Profile System (Planned v4.2.0)

**Design goal:** Support profile-based configuration for APIs, databases, and MCP servers.

**Planned structure:**
```
~/.local/jn/profiles/
├── http/                 # HTTP API profiles
│   └── github.json      # Connection config + auth
├── mcp/                  # MCP server profiles
│   └── github.json
└── sql/                  # Database profiles
    └── mydb/
        ├── config.json
        └── queries/
```

**Planned usage:**
```bash
# With profile
jn cat @github/repos/anthropics/claude-code/issues

# Direct URL (still works)
jn cat https://api.github.com/repos/anthropics/claude-code/issues
```

See `arch/profiles.md` for complete profile system design.

## Plugin Interface

```python
#!/usr/bin/env python3
# /// script
# dependencies = ["library>=1.0.0"]  # PEP 723
# ///
# META: type=source, handles=[".ext"]

def run(config: dict) -> Iterator[dict]:
    """Main entry point. Yields NDJSON records."""
    for line in sys.stdin:
        yield process(line)

def schema() -> dict:
    """Return JSON schema for output (optional)."""
    return {"type": "object"}

def examples() -> list:
    """Return test cases with real data (optional)."""
    return [...]

def test() -> bool:
    """Run outside-in tests (optional)."""
    pass
```

## Example Plugins

### CSV Reader

```python
# plugins/readers/csv_reader.py
# META: type=source, handles=[".csv"]

def run(config):
    """Read CSV from stdin, yield NDJSON."""
    import csv
    reader = csv.DictReader(sys.stdin)
    for row in reader:
        yield dict(row)
```

### HTTP GET

```python
# plugins/http/http_get.py
# META: type=source

def run(config):
    """Fetch from URL, parse JSON."""
    url = config['url']
    result = subprocess.run(['curl', '-sL', url], ...)
    data = json.loads(result.stdout)

    if isinstance(data, list):
        for item in data:
            yield item
    else:
        yield data
```

### jq Filter

```python
# plugins/filters/jq_filter.py
# META: type=filter

def run(config):
    """Transform NDJSON with jq."""
    query = config['query']

    jq_process = subprocess.Popen(
        ['jq', '-c', query],
        stdin=sys.stdin,
        stdout=subprocess.PIPE
    )

    for line in jq_process.stdout:
        yield json.loads(line)
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

import sys
import json
import pyarrow.parquet as pq

def run(config):
    """Read Parquet file, yield NDJSON."""
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

## Registry

The registry (`src/jn/registry.py`) maintains mappings:

```python
class Registry:
    def get_plugin_for_extension(self, ext: str) -> str:
        """Get reader plugin for file extension."""
        # .csv → csv_reader

    def get_plugin_for_url(self, url: str) -> str:
        """Get transport plugin for URL scheme."""
        # s3:// → s3_get

    def get_plugin_for_command(self, cmd: str) -> str:
        """Get shell plugin for command."""
        # ls → ls
```

## Key Principles

- **Standalone scripts** - Can run without framework
- **Regex discovery** - No imports, fast scanning
- **Self-documenting** - META headers, inline tests
- **Language-agnostic** - Any language that uses stdin/stdout
- **Agent-friendly** - Easy to read, modify, generate
- **Zero coupling** - Plugins don't know about each other

See also:
- `arch/backpressure.md` - Streaming details
- `arch/pipeline.md` - Pipeline execution
- `arch/profiles.md` - Profile system design (planned)
