# JN Project - Context for Claude

## What is JN?

JN is an **agent-native ETL framework** that uses:
- **Unix processes + pipes** for streaming (not async/await)
- **NDJSON** as the universal data format
- **Standalone Python plugins** for all data operations
- **Automatic backpressure** via OS pipe buffers
- **UV isolation** for dependency management (no virtualenv hell)

Think: `jn cat data.xlsx | jn filter '.revenue > 1000' | jn put output.csv`

---

## Goals

### Functional Goals
**Universal JSON-based ETL that enables AI agents to create on-demand data tools**

JN allows AI agents (like Claude) to:
- **Extract** data from any source (files, APIs, databases, CLIs)
- **Transform** data with filters and transformations
- **Load** data into any destination format
- **Create plugins on-demand** for new data sources/formats
- **Compose pipelines** naturally via Unix pipes

Unlike traditional ETL tools built for humans, JN is optimized for:
- **Agent discoverability** - Regex-based plugin discovery (no imports)
- **Agent extensibility** - Plugins are simple Python scripts with minimal boilerplate
- **Agent composability** - Standard stdin/stdout/NDJSON everywhere
- **Transparent execution** - Subprocess calls are visible and debuggable

### Non-Functional Goals
**High performance with constant memory usage, regardless of data size**

- **Constant memory**: Process 10GB files with ~1MB RAM usage
- **Streaming by default**: First output appears immediately, not after processing entire dataset
- **Parallel execution**: Multi-stage pipelines run concurrently across CPUs
- **Early termination**: `| head -n 10` stops upstream processing after 10 rows
- **No buffering**: Data flows through pipes, never accumulated in memory

### Architectural Approach
**Leverage the OS for concurrency, backpressure, and resource management**

#### 1. **Backpressure via OS Pipes**
- OS pipe buffers (~64KB) automatically block when full
- Slow downstream consumers pause fast upstream producers
- No manual flow control, queues, or async complexity
- See `spec/arch/backpressure.md` for detailed explanation

#### 2. **UV Python Environment Isolation**
- Each plugin declares dependencies via PEP 723 (`# /// script`)
- UV automatically manages isolated environments per plugin
- No virtualenv activation, no dependency conflicts
- First run downloads deps, subsequent runs are instant

#### 3. **Process-based Parallelism**
- Each pipeline stage runs as a separate process
- True parallelism (not Python GIL-limited threads)
- OS scheduler distributes work across CPUs
- SIGPIPE signal propagates shutdown backward through pipeline

#### 4. **Incorporate, Don't Replace**
- Call existing CLIs directly (`jq`, `curl`, `aws`)
- Don't rewrite tools in Python
- Compose battle-tested Unix utilities
- Plugins are thin wrappers when possible

#### 5. **NDJSON as Universal Format**
- Newline-Delimited JSON (one object per line)
- Streamable (unlike JSON arrays)
- Human-readable and tool-friendly
- Universal interchange format between all plugins

---

## Quick Start

**Install:**
```bash
pip install -e .
```

**Test:**
```bash
make test    # Run all tests
make check   # Code quality checks
```

**Use:**
```bash
jn cat data.csv                    # Read CSV → NDJSON
jn cat data.json | jn put out.csv  # JSON → CSV
jn cat data.csv | jn filter '.revenue > 1000' | jn put filtered.json
```

---

## Project Structure

```
jn/
├── src/jn/              # Core framework
│   ├── cli.py           # Commands: cat, put, filter, plugin, run
│   ├── context.py       # CLI context (JN_HOME, paths)
│   ├── discovery.py     # Plugin discovery with caching
│   ├── registry.py      # Pattern matching for file extensions
│   │
│   ├── commands/        # CLI command implementations
│   │   ├── cat.py       # Read files
│   │   ├── put.py       # Write files
│   │   ├── filter.py    # Apply filters
│   │   ├── head.py      # First N records
│   │   ├── tail.py      # Last N records
│   │   ├── plugin.py    # Plugin management
│   │   └── run.py       # Shorthand for cat with output
│   │
│   └── plugins/         # Built-in plugins (packaged with framework)
│       ├── formats/     # Format readers/writers (read+write in one file)
│       │   ├── csv_.py  # CSV/TSV support
│       │   ├── json_.py # JSON/JSONL/NDJSON support
│       │   └── yaml_.py # YAML support
│       │
│       └── filters/     # Stream transformations
│           └── jq_.py   # JQ filter wrapper
│
├── spec/                # Architecture documentation
│   ├── roadmap.md       # Development roadmap
│   └── arch/            # Architecture deep dives
│       ├── design.md         # v5 architecture overview
│       ├── backpressure.md   # Why Popen > async
│       └── profiles.md       # Future: API/MCP profiles
│
└── tests/               # Test suite (27 tests, all passing)
    ├── conftest.py      # Pytest fixtures
    ├── test_cli.py      # End-to-end CLI tests
    ├── test_cli_new.py  # CLI tests with CliRunner
    ├── test_filter.py   # Filter command tests
    ├── test_plugins.py  # Plugin discovery tests
    └── data/            # Test data files
```

---

## Critical Architecture Decisions

### 1. Use Popen, Not Async

**DO:**
```python
# Streaming with automatic backpressure
reader = subprocess.Popen(
    [sys.executable, plugin.path, "--mode", "read"],
    stdin=infile,
    stdout=subprocess.PIPE
)

writer = subprocess.Popen(
    [sys.executable, plugin.path, "--mode", "write"],
    stdin=reader.stdout,
    stdout=outfile
)

# CRITICAL: Close stdout in parent for SIGPIPE
reader.stdout.close()

# Wait for completion
writer.wait()
reader.wait()
```

**DON'T:**
```python
# NO async/await for data pipelines
# NO subprocess.run(capture_output=True) - buffers everything!
# NO threads - Python GIL kills parallelism
```

**Why:** OS handles concurrency, backpressure, and shutdown automatically. See `spec/arch/backpressure.md`.

### 2. Plugins are Standalone Scripts with PEP 723

**Pattern:**
```python
#!/usr/bin/env -S uv run --script
"""Parse CSV files and convert to/from NDJSON."""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = [
#   ".*\\.csv$",
#   ".*\\.tsv$"
# ]
# ///

import sys
import csv
import json
from typing import Iterator, Optional

def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read CSV from stdin, yield NDJSON records."""
    reader = csv.DictReader(sys.stdin, delimiter=config.get('delimiter', ','))
    yield from reader

def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, write CSV to stdout."""
    records = [json.loads(line) for line in sys.stdin if line.strip()]
    if not records:
        return
    writer = csv.DictWriter(sys.stdout, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['read', 'write'], required=True)
    args = parser.parse_args()

    if args.mode == 'read':
        for record in reads():
            print(json.dumps(record))
    else:
        writes()
```

**Key features:**
- `#!/usr/bin/env -S uv run --script` - UV shebang for direct execution
- `# /// script` - PEP 723 TOML block for dependencies
- `[tool.jn] matches = [...]` - Regex patterns for file matching
- `reads()` and `writes()` - Duck typing determines plugin capabilities
- `--mode` flag - Framework passes read/write mode

**Discovery:** Fast regex parsing of PEP 723 blocks, cached with timestamp-based invalidation.

### 3. NDJSON is the Universal Format

All plugins communicate via NDJSON (one JSON object per line):
```
{"name": "Alice", "age": 30}
{"name": "Bob", "age": 25}
```

**Why NDJSON:**
- Streamable (unlike JSON arrays that require closing `]`)
- Human-readable (easier debugging than binary formats)
- Tool-friendly (works with `jq`, `grep`, line-based processing)
- Constant memory (process one line at a time)

---

## Common Tasks

### Add a New Plugin

1. Create plugin in `src/jn/plugins/formats/` or custom `~/.local/jn/plugins/`
2. Add PEP 723 header with `[tool.jn]` metadata
3. Implement `reads()` and/or `writes()` functions
4. Done - auto-discovered on next run!

Example:
```bash
# Create a new XML plugin
cat > ~/.local/jn/plugins/formats/xml_.py << 'EOF'
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["lxml>=4.9.0"]
# [tool.jn]
# matches = [".*\\.xml$"]
# ///

import sys
import json
from lxml import etree

def reads(config=None):
    tree = etree.parse(sys.stdin)
    for elem in tree.xpath('//record'):
        yield {child.tag: child.text for child in elem}

if __name__ == '__main__':
    for record in reads():
        print(json.dumps(record))
EOF

chmod +x ~/.local/jn/plugins/formats/xml_.py

# Use immediately
jn cat data.xml | jn put output.csv
```

### Read Files
```bash
jn cat data.csv          # Auto-detects .csv extension
jn cat data.json         # Auto-detects .json extension
jn cat data.yaml         # Auto-detects .yaml extension
```

### Convert Formats
```bash
jn cat data.csv | jn put output.json   # CSV → JSON
jn cat data.json | jn put output.yaml  # JSON → YAML
jn cat data.yaml | jn put output.csv   # YAML → CSV
```

### Filter Data
```bash
jn cat data.csv | jn filter '.revenue > 1000' | jn put filtered.csv
jn cat data.json | jn filter 'select(.age > 25)' | jn put adults.json
```

### Limit Output
```bash
jn cat large.csv | jn head 10         # First 10 records
jn cat large.csv | jn tail 20         # Last 20 records
jn cat huge.json | head -n 5          # Unix head works too!
```

### Custom Home Directory
```bash
# Use custom plugin directory (falls back to built-in plugins)
jn --home ~/.my-jn-config cat data.csv

# Set via environment
export JN_HOME=~/.my-jn-config
jn cat data.csv
```

---

## Plugin System

### Plugin Discovery

**Discovery with caching:**
1. Scan `$JN_HOME/plugins/` for `.py` files
2. Parse PEP 723 `[tool.jn]` metadata using regex
3. Cache metadata in `$JN_HOME/cache.json`
4. Timestamp-based invalidation (re-parse if file modified)
5. **Fallback to built-in** if custom plugins dir is empty

**Cache location:**
- Built-in: `src/jn/cache.json`
- Custom: `$JN_HOME/cache.json` or `~/.local/jn/cache.json`

### Pattern Matching

Plugins declare regex patterns they handle:
```toml
[tool.jn]
matches = [
  ".*\\.csv$",     # File extension
  ".*\\.tsv$"      # Alternative extension
]
```

**Registry resolution:**
1. Load all plugins from cache
2. Compile regex patterns
3. Match source file against patterns
4. Select best match (longest pattern wins)

### Plugin Invocation

**Framework invokes plugins as subprocesses:**
```bash
# Read mode
python plugin.py --mode=read < input.csv

# Write mode
python plugin.py --mode=write > output.csv

# Chained
python csv_.py --mode=read < input.csv | python json_.py --mode=write > output.json
```

**Plugin fallback:**
- Commands first check custom plugin directory
- If not found, fall back to built-in plugins
- Enables `--home` flag without copying plugins

---

## Testing Philosophy

**Outside-in testing with real execution:**
- Use real subprocess calls (no mocks)
- Test with actual files
- Validate end-to-end pipelines
- Test both CliRunner and real subprocess execution

**Current status:** 27 tests, all passing ✅

**Test categories:**
1. **CLI tests** (`test_cli.py`) - Real subprocess execution
2. **CliRunner tests** (`test_cli_new.py`) - Click test runner
3. **Filter tests** (`test_filter.py`) - JQ filter integration
4. **Plugin tests** (`test_plugins.py`) - Discovery and caching

**Example test:**
```python
def test_cat_csv_to_json(people_csv, tmp_path):
    """Test: jn cat file.csv output.json."""
    output_file = tmp_path / "output.json"

    # Real subprocess execution
    result = subprocess.run(
        ["uv", "run", "jn", "cat", str(people_csv), str(output_file)],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert output_file.exists()

    with open(output_file) as f:
        data = json.load(f)
    assert len(data) == 5
```

---

## Performance Characteristics

### Memory Usage
| File Size | subprocess.run | Popen + pipes |
|-----------|---------------|---------------|
| 10 MB     | 20 MB         | ~1 MB         |
| 100 MB    | 200 MB        | ~1 MB         |
| 1 GB      | **OOM crash** | ~1 MB         |
| 10 GB     | **OOM crash** | ~1 MB         |

**Memory is constant regardless of file size!**

### Early Termination Example
```bash
# Only processes first 10 rows, stops immediately
jn cat https://example.com/1GB.csv | head -n 10

# Without backpressure: Downloads entire 1GB, processes all rows
# With backpressure: Downloads ~1KB, processes 10 rows, stops ✅
```

### Parallel Execution
```
Pipeline: fetch → parse → filter → write

CPU1: ████████ fetch (downloading)
CPU2:   ████████ parse (parsing)
CPU3:     ████████ filter (jq)
CPU4:       ████████ write (output)

All stages run simultaneously!
```

---

## Architecture Deep Dives

### For Implementation Details
- **`spec/arch/design.md`** - v5 architecture overview, PEP 723, duck typing
- **`spec/arch/backpressure.md`** - Why Popen > async, SIGPIPE, memory comparison
- **`spec/roadmap.md`** - Development roadmap, completed and planned features

### For Code Examples
- **`src/jn/commands/cat.py`** - Pipeline execution with Popen
- **`src/jn/discovery.py`** - Plugin discovery and caching
- **`src/jn/plugins/formats/csv_.py`** - Example format plugin
- **`src/jn/plugins/filters/jq_.py`** - Example filter plugin (wraps jq CLI)

---

## Key Principles

### Unix Philosophy
- **Small, focused plugins** - Each does one thing well
- **stdin → process → stdout** - Standard interface
- **Compose via pipes** - Build complex workflows from simple tools

### Agent-Friendly
- **Plugins are standalone scripts** - No framework imports required
- **Fast discovery** - Regex parsing, no execution or imports
- **Self-documenting** - PEP 723 metadata, clear function signatures
- **Extensible** - AI agents can create new plugins on-demand

### Performance
- **Streaming by default** - Constant memory, regardless of file size
- **Automatic backpressure** - OS pipe buffers handle flow control
- **Parallel execution** - Multi-CPU utilization via processes
- **Early termination** - SIGPIPE propagates shutdown

### Simplicity
- **No async complexity** - No async/await, no event loops
- **No heavy dependencies** - Core framework: click + ruamel.yaml
- **Transparent execution** - Subprocess calls visible via `ps`
- **UV isolation** - No virtualenv activation, no dependency hell

---

## Version Info

- **Current:** v5.0.0-alpha1
- **Branch:** `claude/investigate-skipped-tests-011CUzcnyuYSgUQze7HVcY1G`
- **Python:** >=3.11 (for PEP 723 `tomllib` support)
- **Status:** All 27 tests passing, architecture validated

### Recent Changes
- ✅ Fixed circular import bug (commands importing from cli)
- ✅ Fixed all linting errors (ruff, black)
- ✅ Implemented plugin fallback mechanism
- ✅ Fixed all skipped tests (4 → 0 skipped)
- ✅ Verified architecture matches design goals

### Coming Soon
- **Protocol plugins** - HTTP, S3, FTP sources
- **Profile system** - Named resources (`@github/repos/...`)
- **MCP integration** - Model Context Protocol for API tools
- **SQL plugin** - Database queries as data sources

See `spec/roadmap.md` for complete roadmap.

---

## Development Commands

```bash
# Install with dev dependencies
uv sync --all-extras

# Run tests
make test           # pytest
uv run pytest -v    # verbose

# Code quality
make check          # black + ruff + import-linter

# Format code
uv run black src/jn tests
uv run ruff check --fix src/jn tests

# Coverage
make coverage       # generate coverage report
```

---

## Common Patterns

### Two-Stage Pipeline (cat + put)
```python
# Load plugins with fallback
plugins = get_cached_plugins_with_fallback(ctx.plugin_dir, ctx.cache_path)
registry = build_registry(plugins)

# Resolve plugins
input_plugin = plugins[registry.match(input_file)]
output_plugin = plugins[registry.match(output_file)]

# Start reader
with open(input_file) as infile:
    reader = subprocess.Popen(
        [sys.executable, input_plugin.path, "--mode", "read"],
        stdin=infile,
        stdout=subprocess.PIPE
    )

    # Start writer
    with open(output_file, "w") as outfile:
        writer = subprocess.Popen(
            [sys.executable, output_plugin.path, "--mode", "write"],
            stdin=reader.stdout,
            stdout=outfile
        )

        # CRITICAL: Enable SIGPIPE
        reader.stdout.close()

        # Wait for completion
        writer.wait()
        reader.wait()
```

### Filter Pipeline (stdin → jq → stdout)
```python
# Find jq plugin (with fallback)
jq_plugin = ctx.plugin_dir / "filters" / "jq_.py"
if not jq_plugin.exists():
    jq_plugin = Path(__file__).parent.parent / "plugins" / "filters" / "jq_.py"

# Run filter (inherit stdin/stdout for chaining)
proc = subprocess.Popen(
    [sys.executable, str(jq_plugin), "--query", query],
    stderr=subprocess.PIPE
)
proc.wait()
```

### Direct Plugin Invocation
```python
# Test plugins directly without framework
plugin_path = Path("src/jn/plugins/formats/csv_.py")

with open("data.csv") as f:
    result = subprocess.run(
        [sys.executable, str(plugin_path), "--mode", "read"],
        stdin=f,
        capture_output=True,
        text=True
    )

for line in result.stdout.strip().split("\n"):
    record = json.loads(line)
    print(record)
```
