# Plugin Organization

**Purpose:** Document the plugin structure and vendoring strategy.

---

## Directory Structure

```
plugins/
  readers/           # Source plugins: file format → NDJSON
    csv_reader.py
    json_reader.py
    yaml_reader.py
    xml_reader.py
    toml_reader.py

  writers/           # Target plugins: NDJSON → file format
    csv_writer.py
    json_writer.py
    yaml_writer.py
    xml_writer.py

  filters/           # Transform plugins: NDJSON → NDJSON
    jq_filter.py
    select.py
    map.py
    group_by.py

  shell/             # Shell command wrappers (vendored from JC concepts)
    ls.py            # ls -la → NDJSON
    ps.py            # ps aux → NDJSON
    find.py          # find results → NDJSON
    dig.py           # dig DNS → NDJSON
    netstat.py       # netstat → NDJSON
    du.py            # du disk usage → NDJSON

  http/              # HTTP/API plugins
    http_get.py
    http_post.py
    curl.py
```

---

## Plugin Categories

### Readers (File Format → NDJSON)
**Purpose:** Read structured files and convert to NDJSON stream

**Pattern:**
- Read from stdin or file path
- Parse format (CSV, JSON, YAML, etc.)
- Emit NDJSON records

**Example:** `cat data.csv | plugins/readers/csv_reader.py`

---

### Writers (NDJSON → File Format)
**Purpose:** Convert NDJSON stream to structured file formats

**Pattern:**
- Read NDJSON from stdin
- Collect/buffer as needed
- Write to stdout in target format

**Example:** `... | plugins/writers/csv_writer.py > output.csv`

---

### Filters (NDJSON → NDJSON)
**Purpose:** Transform, filter, or aggregate NDJSON records

**Pattern:**
- Read NDJSON from stdin
- Transform each record (or aggregate)
- Emit NDJSON to stdout

**Example:** `... | plugins/filters/jq_filter.py --query 'select(.amount > 100)'`

---

### Shell (Command → NDJSON)
**Purpose:** Execute shell commands and parse output to NDJSON

**Pattern:**
- Execute command with subprocess
- Parse text output to structured data
- Emit NDJSON records

**Vendored from JC concepts, rewritten for our plugin model:**
- JC parsers typically return `List[Dict]` or `Dict`
- Our plugins stream NDJSON line-by-line
- We add `--test`, `--example`, PEP 723 headers

**Example:** `plugins/shell/ls.py -la /tmp | jq '.filename'`

---

## Vendoring Strategy: JC Parsers → Our Plugins

### What We're Doing

Taking inspiration from JC's parser library but converting to our architecture:

**JC approach:**
- Python library with `jc.parse('ls', text)`
- Returns data structures in memory
- Used programmatically

**Our approach:**
- Standalone CLI plugins
- Execute command directly
- Stream NDJSON output
- Composable with pipes

### Key JC Parsers to Convert

**Tier 1: Essential shell commands (Week 2)**
- `ls` - Directory listings
- `ps` - Process information
- `find` - File search results
- `du` - Disk usage
- `df` - Filesystem information

**Tier 2: Network commands (Week 3)**
- `dig` - DNS queries
- `netstat` - Network connections
- `ping` - Network connectivity
- `ip` - Network configuration
- `ss` - Socket statistics

**Tier 3: System info (Week 4)**
- `systemctl` - Service status
- `journalctl` - System logs (sampled)
- `lsblk` - Block devices
- `mount` - Mount points
- `env` - Environment variables

### Conversion Pattern

**JC parser (library):**
```python
# jc.parsers.ls
def parse(data: str) -> List[Dict]:
    """Parse ls output."""
    lines = data.splitlines()
    results = []
    for line in lines:
        # ... parsing logic ...
        results.append(parsed_item)
    return results
```

**Our plugin (CLI):**
```python
#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
# META: type=source, handles=["ls"]

import subprocess
import json
import sys

def run(config=None):
    """Execute ls and parse to NDJSON."""
    # Execute command
    result = subprocess.run(
        ['ls', '-la'] + (config.get('args', [])),
        capture_output=True,
        text=True
    )

    # Parse output (vendored parsing logic from JC)
    for item in parse_ls_output(result.stdout):
        yield item

def parse_ls_output(text):
    """Parse ls -la output (logic from JC)."""
    # ... parsing implementation ...

def examples():
    return [{"description": "...", "command": "ls.py /tmp"}]

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('args', nargs='*')
    parser.add_argument('--test', action='store_true')
    args = parser.parse_args()

    if args.test:
        test()
    else:
        for record in run({'args': args.args}):
            print(json.dumps(record))
```

---

## Licensing Considerations

**JC License:** MIT (Kelly Brazil)
**Our License:** MIT

**Strategy:**
- We're not copying JC's code verbatim
- We're reimplementing parsing logic in our plugin model
- Attribution in plugin docstrings: "Parsing logic inspired by JC project"
- Each plugin is independent (can be distributed separately)

**Header template:**
```python
"""
Parse ls command output to NDJSON.

Parsing logic inspired by JC project by Kelly Brazil (MIT license).
Reimplemented as standalone CLI plugin for JN.
"""
```

---

## Package Distribution

**Plugins shipped with package:**
```
jn/
  src/jn/              # Core library
  plugins/             # Bundled plugins
    readers/
    writers/
    filters/
    shell/
```

**User plugins:**
```
~/.jn/plugins/         # User-installed
  custom_reader.py
  company_api.py
```

**Discovery order:**
1. User plugins (`~/.jn/plugins/`)
2. Project plugins (`./.jn/plugins/`)
3. Package plugins (installed with jn)
4. System plugins (`/usr/local/share/jn/plugins/`)

---

## pyproject.toml Updates

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/jn"]
include = [
  "plugins/**/*.py"
]

[project]
# ... existing config ...

[project.optional-dependencies]
# Shell parsers don't need extra deps (just subprocess)
shell = []

# Advanced readers need libraries
advanced = [
  "openpyxl>=3.0.0",    # Excel
  "PyYAML>=6.0",        # YAML
  "xmltodict>=0.13.0",  # XML
]
```

---

## Testing Strategy

Each plugin includes:
- `examples()` - Sample inputs/outputs
- `test()` - Built-in test runner
- Integration tests in `tests/integration/test_plugins.py`

**Example test:**
```python
def test_ls_plugin():
    """Test ls plugin produces valid NDJSON."""
    result = subprocess.run(
        ['python3', 'plugins/shell/ls.py', '/tmp'],
        capture_output=True,
        text=True
    )

    # Verify NDJSON output
    lines = result.stdout.strip().split('\n')
    for line in lines:
        data = json.loads(line)  # Must be valid JSON
        assert 'filename' in data
```

---

## Next Steps

1. ✅ Restructure plugins/ directory
2. Create json_reader.py and json_writer.py (passthrough)
3. Create jq_filter.py wrapper
4. Convert first shell command: ls.py
5. Update pyproject.toml to include plugins/
6. Document plugin discovery in src/jn/discovery.py
