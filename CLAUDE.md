# JN Project - Context for Claude

## What is JN?

JN is an **agent-native ETL framework** that uses:
- **Unix processes + pipes** for streaming (not async/await)
- **NDJSON** as the universal data format
- **Standalone Python plugins** for all data operations
- **Automatic backpressure** via OS pipe buffers

Think: `jn cat data.xlsx | jn filter 'select(.revenue > 1000)' | jn put output.csv`

---

## Quick Start

**Build:**
```bash
pip install -e .
```

**Test:**
```bash
pytest
```

**Use:**
```bash
jn cat data.csv                    # Read CSV → NDJSON
jn cat s3://bucket/data.xlsx       # Fetch from S3 → parse → NDJSON
jn cat data.json | jn put out.csv  # JSON → CSV
```

---

## Project Structure

```
jn/
├── src/jn/           # Core framework
│   ├── cli.py        # Commands: cat, put, plugin, profile
│   ├── discovery.py  # Plugin discovery (regex-based)
│   ├── registry.py   # Extension/URL → plugin mapping
│   ├── executor.py   # Popen + pipes execution
│   └── pipeline.py   # Pipeline building
│
├── plugins/          # Data operations (standalone scripts)
│   ├── readers/      # csv_reader, xlsx_reader, json_reader, etc.
│   ├── writers/      # csv_writer, xlsx_writer, json_writer, etc.
│   ├── filters/      # jq_filter
│   ├── http/         # s3_get, http_get, ftp_get
│   └── shell/        # ls, ps, find, etc.
│
├── spec/             # Architecture docs
│   ├── roadmap.md    # What's done, what's next
│   └── arch/         # Architecture details
│       ├── plugins.md      # Plugin system
│       ├── backpressure.md # Streaming with Popen
│       ├── profiles.md     # API/MCP profiles (v4.2.0)
│       └── pipeline.md     # Pipeline execution
│
└── tests/            # Test suite
```

---

## Critical Architecture Decisions

### 1. Use Popen, Not Async

**DO:**
```python
# Streaming with automatic backpressure
process = subprocess.Popen(cmd, stdin=stdin, stdout=subprocess.PIPE)

# CRITICAL: Close stdout in parent for SIGPIPE
prev_process.stdout.close()
```

**DON'T:**
```python
# NO async/await for data pipelines
# NO subprocess.run(capture_output=True) - buffers everything!
```

**Why:** OS handles concurrency, backpressure, and shutdown automatically. See `spec/arch/backpressure.md`.

### 2. Plugins are Standalone Scripts

**Pattern:**
```python
#!/usr/bin/env python3
# /// script
# dependencies = ["library>=1.0"]  # PEP 723
# ///
# META: type=source, handles=[".csv"]

def run(config):
    for line in sys.stdin:
        yield process_line(line)
```

**Discovery:** Regex parsing (no imports needed). See `spec/arch/plugins.md`.

### 3. NDJSON is the Universal Format

All plugins communicate via NDJSON (one JSON object per line):
```
{"name": "Alice", "age": 30}
{"name": "Bob", "age": 25}
```

---

## Common Tasks

**Add a new plugin:**
1. Create `plugins/readers/my_reader.py`
2. Add META header, run() function
3. Done - auto-discovered!

**Read a file:**
```bash
jn cat data.xlsx        # Auto-detects extension
```

**Fetch from URL:**
```bash
jn cat https://api.github.com/repos/anthropics/claude-code/issues
jn cat s3://bucket/file.csv
```

**Convert formats:**
```bash
jn cat data.csv | jn put output.json
jn cat api-response.json | jn put data.xlsx
```

**Filter with jq:**
```bash
jn cat data.csv | jn filter '.revenue > 1000' | jn put filtered.csv
```

---

## Testing Philosophy

**Outside-in testing with real data:**
- Use real public URLs (no mocks)
- Test with actual files
- Validate end-to-end pipelines

Each plugin has inline tests:
```python
def test():
    """Test with real data (NO MOCKS)."""
    url = "https://httpbin.org/json"
    results = list(run({'url': url}))
    assert len(results) > 0
```

---

## Coming Soon (v4.2.0)

### Profile System for APIs/MCP

**Example:**
```bash
# Configure once
~/.local/jn/profiles/http/github.json

# Use forever
jn cat @github/repos/anthropics/claude-code/issues
jn put @github/repos/myuser/myrepo/issues < data.ndjson
```

See `spec/arch/profiles.md` for complete design.

---

## Architecture Deep Dives

**For implementation details, see:**
- `spec/arch/plugins.md` - How plugins work
- `spec/arch/backpressure.md` - Why Popen > async
- `spec/arch/pipeline.md` - How pipelines execute
- `spec/arch/profiles.md` - API/MCP integration (coming)
- `spec/roadmap.md` - What's done, what's next

**For code examples, see:**
- `plugins/http/s3_get.py` - Streaming transport (64KB chunks)
- `plugins/readers/csv_reader.py` - Incremental reader
- `plugins/filters/jq_filter.py` - Streaming filter (Popen stdin→stdout)
- `plugins/writers/csv_writer.py` - Buffering writer
- `src/jn/executor.py` - Pipeline execution reference

---

## Key Principles

**Unix Philosophy:**
- Small, focused plugins
- stdin → process → stdout
- Compose via pipes

**Agent-Friendly:**
- Plugins are standalone scripts
- Regex-based discovery (fast, no execution)
- Self-documenting (META headers, inline tests)

**Performance:**
- Streaming by default (constant memory)
- Automatic backpressure (OS handles it)
- Parallel execution (multi-CPU)

**Simplicity:**
- No async complexity
- No heavy dependencies
- Transparent (subprocess calls visible)

---

## Version Info

- **Current:** v4.0.0-alpha1
- **Branch:** claude/api-plugin-strategy-011CUyR9Mx1yrXG8iBDnUKLK
- **Next:** v4.1.0 (HTTP plugin) → v4.2.0 (MCP plugin)
- See `spec/roadmap.md` for details
