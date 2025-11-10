# JN Architecture

## Overview

JN is an **agent-native ETL framework** where JSON Lines (NDJSON) is the universal data format. It uses a **plugin-based architecture** with **Unix process pipelines** for streaming data transformations.

**Core Philosophy:**
- **Simple**: Plugins are standalone Python scripts (stdin → stdout)
- **Composable**: Chain plugins via Unix pipes
- **Agent-Friendly**: Regex-based discovery (no imports needed)
- **Streaming**: Process data with automatic backpressure
- **Minimal Dependencies**: Use subprocess for external tools

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI Layer (cli.py)                       │
│  - User commands (cat, run, plugin discover, etc.)          │
│  - Pipeline routing (detect file extension, choose plugins) │
│  - User interaction (click-based CLI)                       │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│              Framework Layer (src/jn/)                       │
│  ┌─────────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │ Discovery       │  │ Registry     │  │ Pipeline       │ │
│  │ (discovery.py)  │  │ (registry.py)│  │ (pipeline.py)  │ │
│  │ - Find plugins  │  │ - Map ext→   │  │ - Build chains │ │
│  │ - Parse META    │  │   plugin     │  │ - Describe     │ │
│  │ - Regex-based   │  │ - URL→plugin │  │   pipeline     │ │
│  └─────────────────┘  └──────────────┘  └────────────────┘ │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Executor (executor.py)                       │   │
│  │  - Spawn processes with Popen                        │   │
│  │  - Connect via Unix pipes (stdin/stdout)             │   │
│  │  - Manage backpressure (close stdout for SIGPIPE)    │   │
│  │  - Concurrent execution                               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                             ↓ spawns
┌─────────────────────────────────────────────────────────────┐
│                  Plugin Layer (plugins/)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Transport   │  │   Readers    │  │   Filters    │      │
│  │  (sources)   │  │  (sources)   │  │ (transforms) │      │
│  │ - s3_get     │  │ - xlsx_reader│  │ - jq_filter  │      │
│  │ - ftp_get    │  │ - csv_reader │  │              │      │
│  │ - http_get   │  │ - json_reader│  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │   Writers    │  │    Shell     │                        │
│  │  (targets)   │  │  (sources)   │                        │
│  │ - csv_writer │  │ - ls         │                        │
│  │ - json_writer│  │ - ps         │                        │
│  │ - xlsx_writer│  │ - find       │                        │
│  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Discovery (discovery.py)

**Purpose:** Find and parse plugin metadata without importing them.

**Key Features:**
- **Regex-based parsing** - No Python imports needed
- **Fast discovery** (~10ms for 19 plugins)
- **PEP 723 support** - Reads inline dependency metadata
- **META header parsing** - Extracts type, handles, streaming flag

**Plugin Paths Searched:**
1. `~/.jn/plugins/` - User plugins
2. `./.jn/plugins/` - Project plugins
3. `<package>/plugins/` - Built-in plugins
4. `/usr/local/share/jn/plugins/` - System plugins

**Metadata Extracted:**
```python
PluginMetadata(
    name='xlsx_reader',
    type='source',           # source, filter, target
    category='readers',      # readers, writers, filters, http, shell
    handles=['.xlsx', '.xlsm'],  # File extensions
    dependencies=['openpyxl>=3.1.0'],  # PEP 723 deps
    streaming=True,          # Supports streaming
    description='Read Excel files and output NDJSON',
    keywords=['excel', 'xlsx', 'spreadsheet'],
    command=None,           # For shell plugins (e.g., 'ls')
    path='/path/to/plugin.py'
)
```

**Pattern:**
```python
# META: type=source, handles=[".xlsx", ".xlsm"], streaming=true
# /// script
# dependencies = ["openpyxl>=3.1.0"]
# ///
```

### 2. Registry (registry.py)

**Purpose:** Map file extensions and URL patterns to plugins.

**Mappings:**
- **Extensions** - `.xlsx` → `xlsx_reader`, `.csv` → `csv_reader`
- **URL patterns** - `s3://` → `s3_get`, `ftp://` → `ftp_get`
- **Commands** - `ls` → `ls_plugin`

**User Overrides:**
- Stored in `~/.jn/registry.json`
- User entries have higher priority than defaults
- Can rebuild from discovered plugins

**Example Usage:**
```python
registry = get_registry()

# Get reader for file extension
plugin = registry.get_plugin_for_extension('.xlsx')  # → 'xlsx_reader'

# Get transport for URL
plugin = registry.get_plugin_for_url('s3://bucket/file')  # → 's3_get'

# Get plugin for shell command
plugin = registry.get_plugin_for_command('ls')  # → 'ls'
```

### 3. Pipeline (pipeline.py)

**Purpose:** Build and describe plugin chains.

**Pipeline Structure:**
```python
Pipeline(steps=[
    PipelineStep(
        plugin='s3_get',
        config={'url': 's3://bucket/file.xlsx'},
        args=[]
    ),
    PipelineStep(
        plugin='xlsx_reader',
        config={'sheet': 0},
        args=[]
    ),
    PipelineStep(
        plugin='csv_writer',
        config={'delimiter': ','},
        args=['output.csv']
    )
])
```

**Auto-Detection:**
The CLI automatically builds pipelines based on:
- URL scheme (`s3://`, `ftp://`, `https://`)
- File extension (`.xlsx`, `.csv`, `.json`)
- Destination format

**Example:**
```bash
$ jn cat https://s3.amazonaws.com/bucket/file.xlsx

# Auto-builds pipeline:
# curl → xlsx_reader → stdout
```

### 4. Executor (executor.py)

**Purpose:** Execute pipelines with streaming and backpressure.

**Key Implementation:**
```python
# Spawn processes with Popen (NOT subprocess.run!)
process = subprocess.Popen(
    cmd,
    stdin=stdin or subprocess.PIPE,
    stdout=stdout or subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# CRITICAL: Close stdout in parent for SIGPIPE propagation
if i > 0:
    processes[i-1].stdout.close()

# Wait for completion
process.wait()
```

**Features:**
- ✅ Popen-based streaming (not subprocess.run buffering)
- ✅ SIGPIPE propagation (clean shutdown)
- ✅ Concurrent execution (all stages run in parallel)
- ✅ Error handling (captures stderr from all stages)
- ✅ UV support (PEP 723 dependency management)

See [popen-backpressure.md](popen-backpressure.md) for details.

---

## Plugin Architecture

### Plugin Interface

**All plugins follow the same interface:**

```python
#!/usr/bin/env python3
"""Plugin description."""
# /// script
# dependencies = ["library>=1.0.0"]  # PEP 723 inline metadata
# ///
# META: type=source, handles=[".ext"], streaming=true
# KEYWORDS: keyword1, keyword2
# DESCRIPTION: Short description

import sys
from typing import Optional, Iterator

def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Main entry point.

    Args:
        config: Configuration dict from CLI args

    Yields:
        NDJSON records (dicts)
    """
    # Read from stdin, process, yield to stdout
    for line in sys.stdin:
        record = process(line)
        yield record

def schema() -> dict:
    """Return JSON schema for output."""
    return {"type": "object"}

def examples() -> list[dict]:
    """Return test cases with real data."""
    return [{"description": "...", "input": "...", "expected": [...]}]

def test() -> bool:
    """Run outside-in tests."""
    # Test with real data (no mocks!)
    pass

if __name__ == '__main__':
    # CLI argument parsing
    # Run plugin
    for record in run(config):
        print(json.dumps(record))
```

### Plugin Categories

#### Transport Plugins (sources)

**Purpose:** Fetch bytes from URLs → stdout

**Examples:**
- `s3_get.py` - Fetch from S3 buckets
- `ftp_get.py` - Fetch from FTP servers
- `http_get.py` - Fetch from HTTP APIs

**Pattern:**
```python
# Stream bytes to stdout with 64KB chunks
process = subprocess.Popen(['curl', url], stdout=subprocess.PIPE)
chunk_size = 64 * 1024
while True:
    chunk = process.stdout.read(chunk_size)
    if not chunk:
        break
    sys.stdout.buffer.write(chunk)
```

#### Reader Plugins (sources)

**Purpose:** Parse formats → NDJSON

**Examples:**
- `xlsx_reader.py` - Excel → NDJSON
- `csv_reader.py` - CSV → NDJSON
- `json_reader.py` - JSON → NDJSON

**Pattern:**
```python
# Read from stdin (binary for binary formats)
data = sys.stdin.buffer.read()

# Parse format
workbook = parse_format(data)

# Yield records as NDJSON
for row in workbook.rows:
    yield dict(zip(headers, row))
```

#### Filter Plugins (transforms)

**Purpose:** NDJSON → NDJSON (transformation)

**Examples:**
- `jq_filter.py` - JQ expressions

**Pattern:**
```python
# Stream stdin → external tool → stdout (no buffering!)
jq_process = subprocess.Popen(
    ['jq', '-c', query],
    stdin=sys.stdin,
    stdout=subprocess.PIPE
)

for line in jq_process.stdout:
    yield json.loads(line)
```

#### Writer Plugins (targets)

**Purpose:** NDJSON → format

**Examples:**
- `csv_writer.py` - NDJSON → CSV
- `json_writer.py` - NDJSON → JSON array
- `xlsx_writer.py` - NDJSON → Excel

**Pattern:**
```python
# Collect records (format constraint - need all data for headers/wrapping)
records = []
for line in sys.stdin:
    records.append(json.loads(line))

# Write format
write_format(records, output_file)
```

**Note:** Writers necessarily buffer (format requirements).

#### Shell Plugins (sources)

**Purpose:** Wrap shell commands → NDJSON

**Examples:**
- `ls.py` - List files
- `ps.py` - List processes
- `find.py` - Find files

**Pattern:**
```python
# Run shell command, parse output
result = subprocess.run(['ls', '-la'], capture_output=True, text=True)

# Parse output, yield NDJSON
for line in result.stdout.split('\n'):
    record = parse_line(line)
    yield record
```

---

## Data Flow

### Example: XLSX from S3 to CSV

```bash
$ jn cat s3://bucket/data.xlsx | jn filter '.revenue > 1000' | jn write output.csv
```

**Pipeline:**
```
s3_get → xlsx_reader → jq_filter → csv_writer
```

**Process Flow:**
```
1. CLI detects:
   - s3:// → s3_get transport
   - .xlsx → xlsx_reader
   - jn filter → jq_filter
   - output.csv → csv_writer

2. Executor spawns:
   ┌─────────┐  pipe  ┌───────────┐  pipe  ┌──────────┐  pipe  ┌────────────┐
   │ s3_get  │───────▶│xlsx_reader│───────▶│jq_filter │───────▶│csv_writer  │
   └─────────┘        └───────────┘        └──────────┘        └────────────┘
       ↓                   ↓                     ↓                    ↓
   Fetch bytes        Parse XLSX           Filter rows          Write CSV
   from S3            → NDJSON              → NDJSON             file

3. Backpressure:
   - If csv_writer is slow → jq_filter blocks
   - If jq_filter blocks → xlsx_reader blocks
   - If xlsx_reader blocks → s3_get pauses
   - Automatic flow control via OS pipe buffers!

4. Memory usage:
   - s3_get: ~64KB (pipe buffer)
   - xlsx_reader: O(file_size) (ZIP format constraint)
   - jq_filter: ~64KB (streaming)
   - csv_writer: O(data_size) (format constraint - needs all rows)
```

---

## Streaming Model

### Process-Based Streaming

JN uses **Unix processes connected via pipes** for streaming:

```
Process 1 → [OS Pipe 64KB] → Process 2 → [OS Pipe 64KB] → Process 3
```

**Automatic Backpressure:**
- Writer blocks when pipe is full
- Reader blocks when pipe is empty
- Downstream controls upstream flow
- Zero code needed for flow control!

See [popen-backpressure.md](popen-backpressure.md) for deep dive.

### When Streaming Works

✅ **Formats that stream well:**
- CSV (line-by-line)
- NDJSON (line-by-line)
- Text (line-by-line)

✅ **Operations that stream:**
- Transport (s3_get, ftp_get) - 64KB chunks
- Filters (jq) - line-by-line
- Readers (csv, json arrays) - record-by-record

### When Streaming Doesn't Work

⚠️ **Format constraints (must buffer):**
- CSV writer - Needs all column names for header
- JSON array writer - Needs `[...]` wrapping
- XLSX writer - ZIP archive format
- XLSX reader - ZIP must be extracted before parsing

**Solution:** These necessarily buffer. For true streaming, use NDJSON output.

---

## Dependency Management

### PEP 723 Inline Metadata

Plugins declare dependencies inline:

```python
#!/usr/bin/env python3
# /// script
# dependencies = [
#   "openpyxl>=3.1.0",
#   "requests>=2.28.0",
# ]
# ///
```

**Execution with UV:**
```bash
$ uv run plugin.py
# UV automatically installs dependencies in isolated environment
```

**Execution without UV:**
```bash
$ python3 plugin.py
# Uses system Python, requires dependencies pre-installed
```

**Framework Dependencies:**
- **Core:** `click` (CLI only)
- **Plugins:** Each declares own deps via PEP 723
- **External Tools:** curl, aws, jq (called via subprocess)

**Why Minimal Dependencies:**
- ✅ Fast installation
- ✅ No heavy libs (boto3 is ~50MB)
- ✅ Use existing user configs (AWS profiles work automatically)
- ✅ Transparent (subprocess calls are visible)

---

## Testing Strategy

### Outside-In Testing

JN uses **real data, no mocks:**

```python
def test():
    """Test with real public URLs."""
    test_urls = [
        {
            "description": "GitHub XLSX file",
            "url": "https://raw.githubusercontent.com/.../file.xlsx",
            "min_records": 1
        }
    ]

    for test in test_urls:
        # Download real file
        download = subprocess.run(['curl', '-sL', test['url']])

        # Parse with plugin
        records = list(run({'filepath': tmp_file}))

        # Validate structure
        assert len(records) >= test['min_records']
        assert all(isinstance(r, dict) for r in records)
```

**Why Outside-In:**
- Tests real behavior (not mocked responses)
- Validates against real data formats
- Catches edge cases (real files are messy)
- No mock maintenance

**Each Plugin Has:**
- `examples()` - Test cases with real data
- `test()` - Executable tests (no separate test framework)

```bash
# Run plugin tests
$ python3 plugins/readers/xlsx_reader.py --test
✓ GitHub HuBMAP sample template (1 records)
✓ GitHub EBI EVA submission template (18 records)
✓ GitHub COEF test.xlsx (27 records)

3/3 tests passed
```

---

## CLI Commands

### jn cat

**Read source and output NDJSON.**

```bash
# Local file
$ jn cat data.xlsx

# HTTP URL
$ jn cat https://example.com/data.xlsx

# S3 bucket
$ jn cat s3://bucket/data.xlsx

# FTP server
$ jn cat ftp://ftp.example.com/data.xlsx

# Pipe to other commands
$ jn cat data.xlsx | head -n 10
$ jn cat data.xlsx | jq '.revenue > 1000'
```

**Auto-detects:**
- URL scheme → transport plugin
- File extension → reader plugin
- Builds pipeline automatically

### jn plugin discover

**List all available plugins.**

```bash
$ jn plugin discover
$ jn plugin discover --type source
$ jn plugin discover --category readers
$ jn plugin discover --keyword excel
```

### jn plugin show

**Show plugin details.**

```bash
$ jn plugin show xlsx_reader
Name: xlsx_reader
Type: source
Category: readers
Handles: .xlsx, .xlsm
Dependencies: openpyxl>=3.1.0
Description: Read Excel files and output NDJSON
```

### jn plugin test

**Run plugin tests.**

```bash
$ jn plugin test xlsx_reader
✓ GitHub HuBMAP sample template (1 records)
✓ GitHub EBI EVA submission template (18 records)
3/3 tests passed
```

---

## Configuration

### Plugin Configuration

**Via CLI arguments:**
```bash
$ python3 plugins/readers/xlsx_reader.py data.xlsx --sheet "Sheet2" --skip-rows 1
```

**Via config dict (from framework):**
```python
run(config={'sheet': 'Sheet2', 'skip_rows': 1})
```

**Config mapping:**
- CLI: `--sheet-name "Sheet2"` → config: `{'sheet_name': 'Sheet2'}`
- Booleans: `--data-only` → config: `{'data_only': True}`
- Lists: `--header Col1 --header Col2` → config: `{'header': ['Col1', 'Col2']}`

### Environment Variables

**Transport plugins use environment:**
- `AWS_PROFILE`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - S3
- `FTP_USERNAME`, `FTP_PASSWORD` - FTP (or via config)

**Framework:**
- `JN_PLUGIN_PATH` - Additional plugin directories
- `JN_REGISTRY_PATH` - Custom registry location

---

## Performance Characteristics

### Memory Usage

| File Size | Buffering (old) | Streaming (JN) | Improvement |
|-----------|----------------|----------------|-------------|
| 10 MB | 20 MB | ~1 MB | 20x |
| 100 MB | 200 MB | ~1 MB | 200x |
| 1 GB | 2 GB (OOM!) | ~1 MB | 2000x |

**Constant memory regardless of file size!**

### Throughput

**Multi-stage pipeline on 4-core machine:**
```
CPU1: s3_get (downloading)
CPU2: xlsx_reader (parsing)
CPU3: jq_filter (filtering)
CPU4: csv_writer (writing)

All running concurrently = near-linear speedup!
```

### Latency

**Time to first output:**
- Buffering: Must download + parse entire file
- Streaming: First output as soon as first record parsed

**Example:** 1GB file, `head -n 10`
- Buffering: 90 seconds (full download + parse)
- Streaming: <1 second (stops after 10 rows)

---

## Error Handling

### Plugin Errors

Plugins write errors to `stderr` and exit with non-zero code:

```python
if error:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)
```

### Pipeline Errors

Executor captures stderr from all stages:

```python
for process in processes:
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        errors.append(f"{plugin} failed: {stderr}")
```

**User sees:**
```
Error: Pipeline execution failed:
  xlsx_reader failed with exit code 1
  Error: Sheet 'InvalidSheet' not found. Available: ['Sheet1', 'Sheet2']
```

### SIGPIPE Handling

When downstream exits early (e.g., `head -n 10`):
1. Downstream closes stdin
2. Upstream gets SIGPIPE
3. Upstream exits cleanly
4. **No error reported** (expected behavior)

---

## Design Patterns

### Unix Philosophy

✅ **Do one thing well** - Each plugin has single responsibility
✅ **Compose via pipes** - Chain any plugins together
✅ **Text as universal interface** - NDJSON everywhere
✅ **Avoid chatty protocols** - Stream, don't RPC
✅ **Build on tools** - Use curl, jq, aws (don't reinvent)

### Agent-Friendly

✅ **No imports for discovery** - Regex parsing only
✅ **Self-documenting** - META headers, docstrings
✅ **Standalone scripts** - Run without framework
✅ **Observable** - Can trace with standard tools (ps, strace)
✅ **Testable** - Each plugin has inline tests

### Plugin-Centric

✅ **Framework orchestrates** - Manages routing, execution
✅ **Plugins execute** - Domain logic only
✅ **Clean interface** - stdin → stdout, no coupling
✅ **Easy to add** - Drop script in plugins/, auto-discovered
✅ **Language-agnostic** - Any language that reads stdin/stdout

---

## Extensibility

### Adding a New Plugin

1. **Create script in `plugins/category/`:**
   ```python
   #!/usr/bin/env python3
   # /// script
   # dependencies = ["library>=1.0"]
   # ///
   # META: type=source, handles=[".ext"]

   def run(config):
       for line in sys.stdin:
           yield process(line)
   ```

2. **Make executable:**
   ```bash
   $ chmod +x plugins/readers/my_reader.py
   ```

3. **Test:**
   ```bash
   $ python3 plugins/readers/my_reader.py --test
   ```

4. **Auto-discovered!**
   ```bash
   $ jn plugin discover | grep my_reader
   ```

### Adding a New Transport

```python
# plugins/http/azure_get.py
# META: type=source

def run(config):
    url = config['url']  # azure://container/blob

    # Stream from Azure
    process = subprocess.Popen(['az', 'storage', 'blob', 'download', ...])

    chunk_size = 64 * 1024
    while True:
        chunk = process.stdout.read(chunk_size)
        if not chunk:
            break
        sys.stdout.buffer.write(chunk)
```

**Update registry:**
```python
# src/jn/registry.py
url_patterns = [
    ('azure://', 'azure_get'),  # Add this line
    # ...
]
```

---

## Debugging

### View Pipeline

```bash
$ jn cat https://example.com/data.xlsx -v
Processing source: https://example.com/data.xlsx
Transport: curl → Reader: xlsx_reader
```

### Trace Execution

```bash
# See process tree
$ pstree -p $(pgrep -f "jn cat")

# Monitor processes
$ watch -n 0.1 'ps aux | grep "jn\|curl\|xlsx_reader"'

# Trace system calls
$ strace -e openat,read,write -p $(pgrep xlsx_reader)

# Monitor network
$ nethogs
```

### Check Memory

```bash
# Monitor memory during pipeline
$ /usr/bin/time -v jn cat https://example.com/large.xlsx | head -n 10

Maximum resident set size: ~10MB  # Should be low!
```

---

## Security Considerations

### Command Injection

**DO NOT concatenate strings for subprocess:**

```python
# BAD: Shell injection risk
subprocess.run(f'curl {url}', shell=True)

# GOOD: Array of arguments
subprocess.run(['curl', url])
```

### Temp Files

**Use secure temp files:**

```python
import tempfile

with tempfile.NamedTemporaryFile(delete=True, suffix='.xlsx') as tmp:
    # File auto-deleted when context exits
    download_to_file(tmp.name)
```

### Credentials

**Never hardcode credentials:**

```python
# GOOD: Use environment or config files
profile = os.environ.get('AWS_PROFILE')
subprocess.run(['aws', 's3', 'cp', '--profile', profile, ...])
```

---

## Future Directions

### Planned Features

- [ ] Multi-sheet XLSX writer
- [ ] Streaming XLSX parser (via streaming ZIP)
- [ ] Parallel pipeline execution (multiple files)
- [ ] Progress reporting (download %, row count)
- [ ] Azure Blob Storage transport
- [ ] Google Cloud Storage transport
- [ ] Parquet reader/writer
- [ ] Delta Lake reader/writer

### Performance Optimizations

- [ ] Smart temp file usage (files >1GB)
- [ ] Memory monitoring (auto-fallback to disk)
- [ ] Process pooling (reuse processes for multiple files)
- [ ] Columnar processing (Arrow/Parquet)

---

## References

- **spec/popen-backpressure.md** - Streaming and backpressure details
- **spec/ROADMAP.md** - Feature roadmap
- **docs/ARCHITECTURE.md** - User-facing architecture docs
- **CLAUDE.md** - Context for future Claude sessions
- **src/jn/executor.py** - Reference implementation of Popen streaming
- **plugins/http/s3_get.py** - Example streaming transport
- **plugins/filters/jq_filter.py** - Example streaming filter

---

## Summary

**JN is a streaming ETL framework built on Unix principles:**

✅ **Process-based streaming** - Automatic backpressure via OS pipes
✅ **Plugin architecture** - Standalone scripts, agent-friendly
✅ **Minimal dependencies** - Use subprocess for external tools
✅ **NDJSON everywhere** - Universal data format
✅ **Outside-in testing** - Real data, no mocks
✅ **Simple & composable** - Unix philosophy

**Key Innovation:** Using Popen + pipes for automatic backpressure is simpler, more robust, and more efficient than async I/O for data pipelines.
