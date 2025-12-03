# Python Plugins

> **Purpose**: PEP 723 self-contained plugins for formats and protocols requiring Python ecosystems.

---

## Why Python Plugins?

Some data formats and protocols require Python:

| Plugin | Why Python |
|--------|------------|
| **xlsx** | Excel parsing requires openpyxl/xlrd |
| **xml** | Complex XML handling with lxml |
| **gmail** | Google API client libraries |
| **mcp** | Model Context Protocol SDK |
| **duckdb** | DuckDB Python bindings |
| **parquet** | PyArrow for columnar format |
| **salesforce** | Simple Salesforce library |

Python plugins complement Zig plugins:
- **Zig**: Fast, low-memory, common formats (csv, json, gz, http)
- **Python**: Complex formats, rich ecosystems, rapid development

---

## PEP 723: Inline Script Metadata

Python plugins use PEP 723 for self-contained execution:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl>=3.1.0"]
# [tool.jn]
# matches = [".*\\.xlsx$"]
# role = "format"
# modes = ["read", "write"]
# ///
```

### What This Enables

1. **Self-contained**: Single file, no setup.py or requirements.txt
2. **Isolated execution**: UV creates per-script environments
3. **Dependency declaration**: PEP 723 `dependencies` array
4. **JN metadata**: `[tool.jn]` section for plugin registration

### How It Works

```bash
# Direct execution
./xlsx_.py --mode=read < data.xlsx

# UV handles everything:
# 1. Parses PEP 723 metadata
# 2. Creates isolated environment
# 3. Installs dependencies (cached)
# 4. Runs script
```

---

## Plugin Structure

### Complete Example: XLSX Plugin

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl>=3.1.0"]
# [tool.jn]
# matches = [".*\\.xlsx$", ".*\\.xls$"]
# role = "format"
# modes = ["read", "write"]
# ///
"""Excel format plugin for JN."""

import sys
import json
import argparse
from io import BytesIO

def reads(config=None):
    """Read Excel from stdin, yield NDJSON records."""
    from openpyxl import load_workbook

    # Read binary data from stdin
    data = sys.stdin.buffer.read()
    wb = load_workbook(BytesIO(data), read_only=True)
    ws = wb.active

    # Get headers from first row
    rows = ws.iter_rows(values_only=True)
    headers = [str(h) if h else f"col_{i}" for i, h in enumerate(next(rows))]

    # Yield records
    for row in rows:
        record = {h: v for h, v in zip(headers, row) if v is not None}
        yield record

def writes(config=None):
    """Read NDJSON from stdin, write Excel to stdout."""
    from openpyxl import Workbook

    # Collect all records (Excel requires full data)
    records = [json.loads(line) for line in sys.stdin]
    if not records:
        return

    wb = Workbook()
    ws = wb.active

    # Write headers
    headers = list(records[0].keys())
    ws.append(headers)

    # Write data
    for record in records:
        ws.append([record.get(h) for h in headers])

    # Output binary
    output = BytesIO()
    wb.save(output)
    sys.stdout.buffer.write(output.getvalue())

def main():
    parser = argparse.ArgumentParser(description='Excel format plugin')
    parser.add_argument('--mode', choices=['read', 'write'], required=True)
    parser.add_argument('--jn-meta', action='store_true')
    parser.add_argument('--sheet', help='Sheet name (default: active)')
    args = parser.parse_args()

    if args.jn_meta:
        print(json.dumps({
            "name": "xlsx",
            "version": "0.1.0",
            "matches": [".*\\.xlsx$", ".*\\.xls$"],
            "role": "format",
            "modes": ["read", "write"]
        }))
        return

    if args.mode == 'read':
        for record in reads({'sheet': args.sheet}):
            print(json.dumps(record))
    elif args.mode == 'write':
        writes({'sheet': args.sheet})

if __name__ == '__main__':
    main()
```

---

## Bundled Python Plugins

### xlsx_.py - Excel Format

Handles `.xlsx` and `.xls` files.

```python
# /// script
# dependencies = ["openpyxl>=3.1.0"]
# [tool.jn]
# matches = [".*\\.xlsx$", ".*\\.xls$"]
# role = "format"
# modes = ["read", "write"]
# ///
```

**Features**:
- Read: Any sheet, header detection
- Write: Creates new workbook

### xml_.py - XML Format

Handles `.xml` files with lxml.

```python
# /// script
# dependencies = ["lxml>=5.0.0"]
# [tool.jn]
# matches = [".*\\.xml$"]
# role = "format"
# modes = ["read", "write"]
# ///
```

**Features**:
- Read: Flatten XML to records
- Write: Build XML from records
- XPath support for extraction

### gmail_.py - Gmail Protocol

Accesses Gmail via API.

```python
# /// script
# dependencies = [
#     "google-auth>=2.0.0",
#     "google-auth-oauthlib>=1.0.0",
#     "google-api-python-client>=2.0.0"
# ]
# [tool.jn]
# matches = ["^gmail://"]
# role = "protocol"
# modes = ["read", "profiles"]
# profile_type = "gmail"
# ///
```

**Features**:
- Read messages and threads
- Label filtering
- OAuth2 authentication
- Profile-based configuration

### mcp_.py - Model Context Protocol

Connects to MCP servers.

```python
# /// script
# dependencies = ["mcp>=0.1.0"]
# [tool.jn]
# matches = ["^mcp://"]
# role = "protocol"
# modes = ["read", "profiles"]
# profile_type = "mcp"
# ///
```

**Features**:
- Tool invocation
- Resource access
- Server discovery
- Profile-based configuration

### duckdb_.py - DuckDB Database

Queries DuckDB databases.

```python
# /// script
# dependencies = ["duckdb>=0.9.0"]
# [tool.jn]
# matches = ["^duckdb://", ".*\\.duckdb$"]
# role = "database"
# modes = ["read", "profiles"]
# profile_type = "duckdb"
# ///
```

**Features**:
- SQL query execution
- Table discovery as profiles
- Schema introspection
- Streaming results

### parquet_.py - Parquet Format

Handles Apache Parquet files.

```python
# /// script
# dependencies = ["pyarrow>=14.0.0"]
# [tool.jn]
# matches = [".*\\.parquet$"]
# role = "format"
# modes = ["read", "write"]
# ///
```

**Features**:
- Columnar format support
- Schema preservation
- Compression options

---

## Writing a Python Plugin

### Minimal Template

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = [".*\\.myformat$"]
# role = "format"
# modes = ["read"]
# ///

import sys
import json
import argparse

def reads(config=None):
    """Read format from stdin, yield records."""
    for line in sys.stdin:
        yield {"data": line.strip()}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['read', 'write'])
    parser.add_argument('--jn-meta', action='store_true')
    args = parser.parse_args()

    if args.jn_meta:
        print(json.dumps({
            "name": "myformat",
            "matches": [".*\\.myformat$"],
            "role": "format",
            "modes": ["read"]
        }))
    elif args.mode == 'read':
        for record in reads():
            print(json.dumps(record))

if __name__ == '__main__':
    main()
```

### With Profile Support

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["some-api-client"]
# [tool.jn]
# matches = ["^myprotocol://"]
# role = "protocol"
# modes = ["read", "profiles"]
# profile_type = "myprotocol"
# ///

import sys
import json
import argparse

def reads(config=None):
    """Fetch data from protocol."""
    # Use config for connection details
    pass

def profiles_list(config=None):
    """List available profiles."""
    yield {"reference": "@myprotocol/endpoint1", "description": "..."}
    yield {"reference": "@myprotocol/endpoint2", "description": "..."}

def profiles_info(config=None):
    """Get profile details."""
    return {
        "reference": config.get('profile'),
        "params": ["limit", "offset"],
        "defaults": {"limit": 100}
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['read', 'profiles'])
    parser.add_argument('--jn-meta', action='store_true')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--info')
    args = parser.parse_args()

    if args.jn_meta:
        print(json.dumps({
            "name": "myprotocol",
            "matches": ["^myprotocol://"],
            "role": "protocol",
            "modes": ["read", "profiles"],
            "profile_type": "myprotocol"
        }))
    elif args.mode == 'profiles':
        if args.list:
            for p in profiles_list():
                print(json.dumps(p))
        elif args.info:
            print(json.dumps(profiles_info({'profile': args.info})))
    elif args.mode == 'read':
        for record in reads():
            print(json.dumps(record))

if __name__ == '__main__':
    main()
```

---

## Best Practices

### Streaming When Possible

```python
# GOOD: Stream records
def reads(config=None):
    for item in api_client.iterate():
        yield transform(item)

# BAD: Load everything first
def reads(config=None):
    all_data = api_client.get_all()  # Memory!
    return [transform(item) for item in all_data]
```

### Handle Binary Data

For binary formats, use buffer:

```python
# Reading binary
data = sys.stdin.buffer.read()

# Writing binary
sys.stdout.buffer.write(binary_data)
```

### Graceful Error Handling

```python
def reads(config=None):
    try:
        for item in source:
            yield process(item)
    except SomeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
```

### SIGPIPE Handling

```python
import signal

# Ignore SIGPIPE for clean exit
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
```

---

## Plugin Discovery

JN discovers Python plugins by:

1. **Scanning directories**: `~/.local/jn/plugins/python/`, `$JN_HOME/plugins/python/`
2. **Finding `.py` files**: With UV shebang
3. **Parsing PEP 723**: Extract `[tool.jn]` block
4. **No execution**: Metadata parsed from text

### Discovery Example

```
File: ~/.local/jn/plugins/python/salesforce_.py

Parsed metadata:
{
  "name": "salesforce",
  "matches": ["^salesforce://"],
  "role": "protocol",
  "modes": ["read"]
}

Registered:
  Pattern: ^salesforce:// → salesforce_.py
```

---

## Testing Plugins

### Direct Execution

```bash
# Test read mode
echo "test data" | ./myplugin_.py --mode=read

# Test metadata
./myplugin_.py --jn-meta | jq .

# Test with file
./xlsx_.py --mode=read < test.xlsx | head -5
```

### Via JN

```bash
# After placing in plugin directory
jn cat test.xlsx | jn head -n 5
jn cat @myapi/endpoint | jn table
```

### Unit Tests

```python
def test_reads():
    from io import StringIO
    sys.stdin = StringIO("test,data\n1,2\n")
    records = list(reads())
    assert len(records) == 1
    assert records[0]['test'] == '1'
```

---

## Plugin Locations

Python plugins live in:

```
Priority Order:

1. .jn/plugins/python/           # Project plugins
2. ~/.local/jn/plugins/python/   # User plugins
3. $JN_HOME/plugins/python/      # Bundled plugins
```

### Bundled Plugins

```
$JN_HOME/plugins/python/
├── xlsx_.py
├── xml_.py
├── gmail_.py
├── mcp_.py
├── duckdb_.py
└── parquet_.py
```

### User Plugins

```
~/.local/jn/plugins/python/
├── salesforce_.py     # Custom Salesforce
├── snowflake_.py      # Custom Snowflake
└── internal_api_.py   # Company-specific
```

---

## Design Rationale

### Why PEP 723?

- **Standard**: Official Python packaging standard
- **Self-contained**: No external files needed
- **UV integration**: Automatic environment management
- **Parseable**: Metadata extracted without execution

### Why Separate from Zig?

- **Ecosystem access**: Python has libraries for everything
- **Rapid development**: Write, test, iterate quickly
- **Complexity handling**: OAuth, complex formats, SDKs

### Why Keep Both?

```
Zig Plugins          Python Plugins
    │                     │
    ▼                     ▼
Fast, common         Complex, ecosystem
(csv, json, gz)      (xlsx, gmail, mcp)
    │                     │
    └─────────┬───────────┘
              │
        Same interface
        Same discovery
        Same pipelines
```

Both types work identically from JN's perspective.

---

## See Also

- [05-plugin-system.md](05-plugin-system.md) - Plugin interface
- [04-project-layout.md](04-project-layout.md) - Plugin locations
- [07-profiles.md](07-profiles.md) - Profile mode support
