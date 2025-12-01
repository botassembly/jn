---
name: jn-etl
description: Expert in JN agent-native ETL framework. Create data pipelines, develop format/protocol plugins, convert between CSV/JSON/YAML/Excel, fetch from APIs, and stream data processing. Use when working with data transformation, ETL pipelines, plugin development, or any data format conversion tasks.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# JN ETL Framework Expert

## Core Philosophy

JN is an agent-native ETL framework built on three principles:
1. **NDJSON Everywhere** - Universal interchange format (one JSON object per line)
2. **OS Pipes for Backpressure** - Use `subprocess.Popen`, never async/await
3. **Standalone Plugins** - UV-isolated scripts with PEP 723 dependencies

## Critical Rules

### ALWAYS Use JN Commands (Golden Path)

**✅ CORRECT:**
```bash
jn cat data.csv | jn filter '.age > 25' | jn put output.json
jn cat https://api.com/data~json | jn head -n 10
jn cat data.xlsx | jn put results.csv
```

**❌ NEVER DO THIS:**
```bash
python csv_.py --mode read < data.csv  # Bypasses framework!
uv run csv_.py --mode read             # Loses backpressure!
```

**Why?** Direct plugin calls bypass automatic backpressure, early termination, parallel execution, and proper error handling.

## Instructions

### When Creating Data Pipelines

1. **Use JN Commands**: Always use `jn cat`, `jn put`, `jn filter`, never call plugins directly
2. **Leverage Streaming**: Pipelines handle any file size with constant ~1MB memory
3. **Chain with Pipes**: Compose `jn cat | jn filter | jn put` for multi-stage processing
4. **Early Termination**: Add `| head -n N` to stop processing after N records

### When Developing Plugins

1. **Check Plugin Structure**: Read existing plugins in `jn_home/plugins/` for patterns
2. **Use PEP 723 Header**:
   ```python
   #!/usr/bin/env -S uv run --script
   # /// script
   # requires-python = ">=3.11"
   # dependencies = ["pandas>=2.0"]
   # [tool.jn]
   # matches = [".*\\.csv$", ".*\\.tsv$"]
   # ///
   ```

3. **Implement Duck-Typed Functions**:
   - `reads(config=None)` - Read from stdin, yield NDJSON dicts
   - `writes(config=None)` - Read NDJSON from stdin, write format to stdout
   - Both are generators that stream data line-by-line

4. **CLI Interface**:
   ```python
   if __name__ == '__main__':
       import sys
       mode = sys.argv[sys.argv.index('--mode') + 1] if '--mode' in sys.argv else 'read'
       if mode == 'read':
           for record in reads():
               print(json.dumps(record))
       else:
           for record in writes():
               sys.stdout.write(record)
   ```

5. **Validate Plugin**:
   ```bash
   jn check plugin path/to/plugin.py  # AST-based security validation
   ```

### When Using Advanced Features

**Universal Addressing:**
```bash
jn cat data.csv                      # Local file
jn cat data.csv.gz                   # Auto-detect compression
jn cat https://api.com/data~json     # HTTP with format hint
jn cat "mcp://server/resource"       # MCP protocol
```

**Profile System (for APIs):**
```bash
jn profile list                      # Show available profiles
jn cat http://myapi/users            # Uses profile for auth
jn profile discover https://api.com  # Auto-discover endpoints
```

**Shell Integration:**
```bash
jn sh "ps aux" | jn filter '.cpu > 50'   # Shell command → NDJSON
jn sh "ls -la" | jn put files.json       # Convert any CLI output
```

**Analysis & Introspection:**
```bash
jn inspect data.csv                  # Analyze data structure
jn analyze < data.ndjson             # Schema and statistics
```

## Architecture Patterns

### Two-Stage Pipeline (Read → Write)
```python
import subprocess, sys
from pathlib import Path

# Resolve plugins
reader_plugin = resolve_plugin(input_path)
writer_plugin = resolve_plugin(output_path)

# Start processes
reader = subprocess.Popen(
    [sys.executable, reader_plugin.path, "--mode", "read"],
    stdin=input_file,
    stdout=subprocess.PIPE
)

writer = subprocess.Popen(
    [sys.executable, writer_plugin.path, "--mode", "write"],
    stdin=reader.stdout,
    stdout=output_file
)

# CRITICAL: Close reader stdout in parent for SIGPIPE
reader.stdout.close()

# Wait for completion
writer.wait()
reader.wait()
```

### Filter Pipeline (Read → Filter → Write)
```python
# Chain three processes
reader = subprocess.Popen([...], stdout=subprocess.PIPE)
filter_proc = subprocess.Popen([...], stdin=reader.stdout, stdout=subprocess.PIPE)
writer = subprocess.Popen([...], stdin=filter_proc.stdout, stdout=output)

reader.stdout.close()      # Enable SIGPIPE backpressure
filter_proc.stdout.close()

writer.wait()
filter_proc.wait()
reader.wait()
```

## Common Tasks

### Task: Convert Data Format
```bash
jn cat input.csv | jn put output.json      # CSV → JSON
jn cat input.yaml | jn put output.csv      # YAML → CSV
jn cat input.xlsx | jn put output.json     # Excel → JSON
```

### Task: Filter and Transform
```bash
jn cat data.csv | jn filter '.revenue > 1000' | jn put high_value.json
jn cat data.json | jn filter 'select(.active == true)' | jn put active_users.csv
```

### Task: Fetch from API
```bash
jn cat https://api.github.com/users~json | jn head -n 5
jn cat http://myapi/users | jn filter '.age > 25' | jn put filtered.json
```

### Task: Create Custom Plugin
```bash
# 1. Create plugin file
cat > jn_home/plugins/formats/my_format.py << 'EOF'
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = [".*\\.myext$"]
# ///

import json
import sys

def reads(config=None):
    """Read custom format, yield NDJSON."""
    for line in sys.stdin:
        # Parse your format here
        yield {"data": line.strip()}

def writes(config=None):
    """Read NDJSON, write custom format."""
    for line in sys.stdin:
        record = json.loads(line)
        # Write your format here
        print(f"Custom: {record}")

if __name__ == '__main__':
    mode = sys.argv[sys.argv.index('--mode') + 1] if '--mode' in sys.argv else 'read'
    if mode == 'read':
        for record in reads():
            print(json.dumps(record))
    else:
        for _ in writes():
            pass
EOF

# 2. Make executable
chmod +x jn_home/plugins/formats/my_format.py

# 3. Validate
jn check plugin jn_home/plugins/formats/my_format.py

# 4. Use it
jn cat data.myext | jn put output.json
```

## Key Files Reference

**Core Commands:**
- `src/jn/cli/commands/cat.py` - Read data sources
- `src/jn/cli/commands/put.py` - Write data outputs
- `src/jn/cli/commands/filter.py` - Apply transformations
- `src/jn/cli/commands/run.py` - Orchestrate pipelines

**Plugin System:**
- `src/jn/plugins/discovery.py` - Plugin discovery via regex
- `src/jn/plugins/registry.py` - Pattern matching
- `src/jn/addressing/parser.py` - Universal addressing

**Example Plugins:**
- `jn_home/plugins/formats/csv_.py` - CSV format plugin
- `jn_home/plugins/formats/json_.py` - JSON format plugin
- `jn_home/plugins/protocols/http_.py` - HTTP protocol plugin

**Architecture Docs:**
- `spec/done/arch-design.md` - v5 architecture overview
- `spec/done/arch-backpressure.md` - Why Popen beats async
- `spec/done/plugin-specification.md` - Plugin development guide

## Testing

```bash
# Run tests
make test

# Check code quality
make check

# Test specific plugin
jn check plugin jn_home/plugins/formats/csv_.py

# Test pipeline end-to-end
echo '{"x":1}' | jn cat - | jn put -
```

## Examples

### Example 1: CSV Analysis Pipeline
```bash
# Read CSV, filter high values, compute stats, save as JSON
jn cat sales.csv | \
  jn filter '.amount > 1000' | \
  jn analyze | \
  jn put summary.json
```

### Example 2: Multi-Source Aggregation
```bash
# Combine local file + API data
jn cat local.csv > /tmp/combined.ndjson
jn cat https://api.com/data~json >> /tmp/combined.ndjson
jn cat /tmp/combined.ndjson | jn put output.json
```

### Example 3: Shell Command Processing
```bash
# Process list → filter → export
jn sh "ps aux" | \
  jn filter '.cpu > 50' | \
  jn put high_cpu.csv
```

### Example 4: API to Database ETL
```bash
# Fetch from API, transform, load to CSV for database import
jn cat http://api/users | \
  jn filter 'select(.active) | {id, name, email}' | \
  jn put users_import.csv
```

## Troubleshooting

**Memory Issues:** Plugins should stream, never load entire dataset into memory

**Performance:** Check that `reader.stdout.close()` is called for SIGPIPE backpressure

**Plugin Not Found:** Run `jn plugin list` to verify discovery, check regex patterns in `[tool.jn]`

**Format Detection:** Use explicit format hint: `jn cat data~csv` or `jn put output~json`
