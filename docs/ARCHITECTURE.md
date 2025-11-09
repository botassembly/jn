# JN Architecture

**Version:** 4.0.0-alpha1
**Architecture:** Function-Based Plugin System with Regex Discovery
**Philosophy:** Agent-native ETL with JSON Lines everywhere

---

## Core Principles

### 1. JSON Lines Everywhere
Universal data interchange format on the CLI. Every plugin reads/writes NDJSON (Newline-Delimited JSON), enabling perfect Unix pipe composition.

### 2. Discoverable Without Execution
Plugins are files on disk with parseable `# META:` headers. Discovery happens via filesystem scanning and regex parsing - no Python imports needed.

### 3. Automatic Pipeline Construction
Framework wires together sources → filters → targets automatically based on file extensions, URL patterns, and command names.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                            │
│  (Click framework - 10 commands)                            │
│  discover, show, which, run, paths, cat, put,               │
│  create, test, validate                                     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                     Core Libraries                          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Discovery   │  │  Registry    │  │  Pipeline    │    │
│  │              │  │              │  │              │    │
│  │ • Scan paths │  │ • Extension  │  │ • Build      │    │
│  │ • Parse META │  │   mapping    │  │ • Describe   │    │
│  │ • Cache      │  │ • URL routes │  │ • Auto-      │    │
│  │              │  │ • Persist    │  │   detect     │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Executor                                │  │
│  │                                                      │  │
│  │  • Unix pipe composition                            │  │
│  │  • Subprocess isolation                             │  │
│  │  • UV dependency management                         │  │
│  │  • Error handling                                   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    Plugin Ecosystem                         │
│                                                             │
│  plugins/                                                   │
│    readers/      (8 plugins)  - Read files → NDJSON        │
│    writers/      (6 plugins)  - NDJSON → Write files       │
│    filters/      (1 plugin)   - NDJSON → NDJSON            │
│    shell/        (7 plugins)  - Commands → NDJSON          │
│    http/         (1 plugin)   - HTTP APIs → NDJSON         │
│                                                             │
│  Each plugin is a standalone Python script with:           │
│    • PEP 723 inline dependencies                           │
│    • run() function (main logic)                           │
│    • examples() function (test cases)                      │
│    • test() function (self-test)                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Module Deep Dive

### Discovery System (`src/jn/discovery.py`)

**Purpose:** Find plugins without importing Python code

**How it works:**
```python
# Scan plugin directories
scan_paths = [
    Path.home() / '.jn/plugins',      # User plugins
    Path.cwd() / 'plugins',            # Project plugins
    Path(__file__).parent / 'plugins', # Package plugins
    Path('/usr/local/share/jn/plugins') # System plugins
]

# Parse metadata with regex (no imports!)
# META: type=source, handles=[".csv", ".tsv"], streaming=true
pattern = r'# META: type=(\w+)(?:, (.+))?'

# Build plugin registry
{
  'csv_reader': {
    'path': '/path/to/csv_reader.py',
    'type': 'source',
    'handles': ['.csv', '.tsv'],
    'streaming': True,
    'modified': 1699564800.0
  },
  ...
}
```

**Key features:**
- Fast scanning (~10ms for 19 plugins)
- No Python imports = no import errors
- Cache based on file modification times
- Supports user/project/package/system plugin paths

### Registry System (`src/jn/registry.py`)

**Purpose:** Map file extensions/URLs/commands to plugins

**Storage:** `~/.jn/registry.json`

```json
{
  "extensions": {
    ".csv": "csv_reader",
    ".json": "json_reader",
    ".yaml": "yaml_reader",
    ".xml": "xml_reader",
    ".toml": "toml_reader"
  },
  "url_patterns": {
    "^https?://": "http_get",
    "^s3://": "s3_reader"
  },
  "commands": {
    "ls": "ls",
    "ps": "ps",
    "df": "df"
  }
}
```

**Key features:**
- Automatic extension detection
- URL pattern matching (regex)
- Command name resolution
- Priority system for conflicts
- Persistent across sessions

### Pipeline System (`src/jn/pipeline.py`)

**Purpose:** Build and describe pipelines

**Pipeline Structure:**
```python
@dataclass
class PipelineStep:
    type: str      # 'source', 'filter', or 'target'
    plugin: str    # Plugin name
    config: dict   # Plugin configuration
    args: list     # Command-line args

@dataclass
class Pipeline:
    steps: list[PipelineStep]
```

**Auto-detection:**
```python
def auto_detect_pipeline(source: str, target: str) -> Pipeline:
    """Build pipeline from source/target hints."""
    pipeline = Pipeline()

    # Detect source plugin
    if source.startswith('http'):
        pipeline.add_source('http_get', {'url': source})
    elif Path(source).suffix == '.csv':
        pipeline.add_source('csv_reader', {'file': source})

    # Detect target plugin
    if Path(target).suffix == '.json':
        pipeline.add_target('json_writer', {'output': target})

    return pipeline
```

### Executor System (`src/jn/executor.py`)

**Purpose:** Execute pipelines via Unix pipes

**Execution model:**
```python
# Build command for each step
cmd = ['python', plugin_path]  # or ['uv', 'run', plugin_path]

# Chain with Unix pipes
process1 | process2 | process3

# Example: CSV → jq filter → JSON
csv_reader data.csv | jq '.name' | json_writer output.json
```

**Key features:**
- Subprocess isolation (no shared state)
- UV manages dependencies per plugin
- Binary-safe streaming (no Python buffering)
- Error handling with detailed messages

---

## Plugin Architecture

### Plugin Structure

Every plugin is a standalone Python script:

```python
#!/usr/bin/env python3
"""CSV reader - Convert CSV to NDJSON."""
# /// script
# dependencies = []
# ///
# META: type=source, handles=[".csv", ".tsv"], streaming=true

import sys
import json
from typing import Iterator, Optional

def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Main plugin logic."""
    config = config or {}
    # Read CSV from stdin
    # Yield records as dicts
    for row in csv.DictReader(sys.stdin):
        yield row

def examples() -> list[dict]:
    """Test cases."""
    return [...]

def test() -> bool:
    """Self-test."""
    # Run examples and verify
    return True

if __name__ == '__main__':
    # CLI mode - run plugin
    for record in run():
        print(json.dumps(record))
```

### Plugin Types

**Sources (readers/):**
- Read data from files, APIs, commands
- Output NDJSON to stdout
- Examples: csv_reader, yaml_reader, http_get, ls

**Filters (filters/):**
- Transform NDJSON stream
- Read NDJSON from stdin, write NDJSON to stdout
- Examples: jq_filter

**Targets (writers/):**
- Write NDJSON to output format
- Read NDJSON from stdin, write to file/stdout
- Examples: csv_writer, json_writer, yaml_writer

### PEP 723 Dependencies

Plugins declare dependencies inline:

```python
# /// script
# dependencies = [
#   "pyyaml>=6.0",
#   "requests>=2.28.0",
# ]
# ///
```

UV automatically creates isolated environments and installs dependencies when running plugins.

---

## Data Flow

### Example: CSV → Filter → JSON

```bash
jn cat data.csv | jq '.age > 18' | jn put adults.json
```

**Execution:**
```
1. jn cat data.csv
   → Registry: .csv → csv_reader
   → Execute: python plugins/readers/csv_reader.py < data.csv
   → Output: NDJSON stream

2. jq '.age > 18'
   → Unix pipe: NDJSON in, NDJSON out
   → Filter records

3. jn put adults.json
   → Registry: .json → json_writer
   → Execute: python plugins/writers/json_writer.py > adults.json
   → Output: JSON array file
```

---

## Design Decisions

### Why Function-Based Plugins?

**Not classes:**
- Simpler mental model
- Less boilerplate
- Easier for agents to generate
- Duck-typing over inheritance

**Benefits:**
- 50-100 LOC per plugin
- Self-contained (no shared state)
- Easy to test (examples() function)
- Easy to create (templates)

### Why Regex Discovery?

**Not Python imports:**
- Broken imports don't break discovery
- Fast (no module loading)
- Works across Python versions
- Enables static analysis

**Benefits:**
- 10ms to scan 19 plugins
- No import errors
- Can discover broken plugins
- Easy to implement

### Why Unix Pipes?

**Not Python processing:**
- O(1) memory usage
- Binary-safe streaming
- Leverages OS process isolation
- Standard Unix composition

**Benefits:**
- Handle GB-sized files
- No memory limits
- Process isolation = no conflicts
- Standard debugging (strace, etc.)

### Why UV?

**Not virtualenv/pip:**
- Fast dependency resolution
- Per-script isolation
- Declarative (PEP 723)
- No global state

**Benefits:**
- Plugins can't conflict
- Easy to distribute
- Reproducible builds
- Modern Python tooling

---

## Performance Characteristics

**Discovery:**
- 19 plugins: ~10ms
- 100 plugins: ~50ms
- 1000 plugins: ~500ms

**Execution:**
- Memory: O(1) - streaming only
- CPU: Bound by plugin logic
- I/O: Limited by pipes (~5 GB/s)

**Scaling:**
- Plugins: Unlimited (filesystem scan)
- Data size: Unlimited (streaming)
- Concurrent pipelines: Limited by OS

---

## Extension Points

### Add a new plugin type

1. Add type to discovery regex
2. Update pipeline builder
3. Create template
4. Document in plugins/README.md

### Add a new registry type

1. Add to Registry model
2. Update resolve_plugin()
3. Add CLI commands
4. Persist to registry.json

### Add a new executor mode

1. Add method to PipelineExecutor
2. Update CLI commands
3. Add tests
4. Document usage

---

## Testing Strategy

### Outside-In Testing

Test from the CLI down (no private unit tests):

```python
def test_cat_csv_file(runner):
    """Test jn cat with CSV file."""
    result = runner.invoke(main, ['cat', 'data.csv'])
    assert result.exit_code == 0
    # Verify NDJSON output
```

### Plugin Self-Tests

Every plugin tests itself:

```python
def test() -> bool:
    """Run built-in tests."""
    for test_case in examples():
        # Mock stdin/stdout
        # Run plugin
        # Verify output
    return all_passed
```

### Coverage Targets

- CLI commands: 75%+
- Core modules: 85%+
- Overall: 75%+

---

## Future Directions

### Planned Features

1. **Database plugins** - PostgreSQL, MySQL, SQLite readers/writers
2. **Excel support** - Read/write .xlsx files
3. **S3 integration** - Read/write from cloud storage
4. **MCP integration** - Expose plugins as MCP tools
5. **Advanced filters** - Aggregations, group-by, joins

### Architectural Evolution

1. **Streaming protocol** - Binary format for efficiency
2. **Remote plugins** - HTTP-based plugin execution
3. **Plugin marketplace** - Discover/install community plugins
4. **Visual builder** - GUI for pipeline construction
5. **Agent SDK** - First-class agent integration

---

## References

- [README.md](../README.md) - User documentation
- [plugins/README.md](../plugins/README.md) - Plugin development guide
- [COVERAGE_REVIEW.md](../COVERAGE_REVIEW.md) - Test coverage analysis
- [spec/IMPLEMENTATION_PLAN.md](../spec/IMPLEMENTATION_PLAN.md) - Development roadmap
