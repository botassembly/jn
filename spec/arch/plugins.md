# Plugin System

## Overview

JN plugins are **standalone Python scripts** that follow stdin → process → stdout pattern. They're discovered via regex (no imports), self-document via META headers, and declare dependencies via PEP 723.

## Plugin Discovery

**Locations searched (priority order):**
1. `~/.local/jn/plugins/` (or custom JN_HOME)
2. `./.jn/plugins/` (project-specific)
3. `<package>/plugins/` (built-in)

**Discovery method:** Regex parsing of file contents
- No Python imports needed
- Fast (~10ms for 19 plugins)
- Extracts META headers, PEP 723 deps, docstrings

**Example META header:**
```python
# META: type=source, handles=[".csv"], streaming=true
# KEYWORDS: csv, data, parsing
# DESCRIPTION: Read CSV files and output NDJSON
```

## Plugin Types

**Sources** - Read data → output NDJSON
- Readers: Parse file formats (csv_reader, xlsx_reader)
- Transports: Fetch from URLs (s3_get, http_get, ftp_get)
- Shell: Execute commands (ls, ps, find)

**Filters** - Transform NDJSON → NDJSON
- Example: jq_filter (JSON filtering/transformation)

**Targets** - Read NDJSON → write output
- Writers: Generate file formats (csv_writer, json_writer)

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

## Registry

Maps extensions/URLs to plugins:
- `.csv` → `csv_reader`
- `s3://` → `s3_get`
- `https://*.xlsx` → `http_get` + `xlsx_reader`

## Key Principles

- **Standalone scripts** - Can run without framework
- **Regex discovery** - No imports, fast scanning
- **Self-documenting** - META headers, inline tests
- **Language-agnostic** - Any language that uses stdin/stdout
- **Agent-friendly** - Easy to read, modify, generate

See also: `arch/backpressure.md` for streaming details
