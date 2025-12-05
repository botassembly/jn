# JN Demos

Run these demos to see JN's ETL capabilities in action. Each demo has a well-commented script showing how to use JN.

## Prerequisites

Before running demos, build the Zig tools:

```bash
cd ..
make build
export JN_HOME="$(pwd)"
export PATH="$(pwd)/tools/zig/jn/bin:$PATH"
```

## Quick Start

```bash
cd csv-filtering && ./run_examples.sh     # Core ETL operations ✅
cd join && ./run_examples.sh              # Stream enrichment via hash join ✅
cd shell-commands && ./run_examples.sh    # Convert shell output to NDJSON ⚠️
```

## Available Demos

| Demo | Status | Description |
|------|--------|-------------|
| **csv-filtering/** | ✅ Working | Read CSV, filter with ZQ, convert formats |
| **join/** | ✅ Working | Stream enrichment via hash join |
| **shell-commands/** | ⚠️ Partial | Requires `jc` tool, ZQ subset limitations |
| **http-api/** | ⚠️ Limited | HTTP URLs pending OpenDAL integration |
| **glob/** | ⚠️ Limited | Glob patterns pending implementation |
| **xlsx-files/** | ❌ Pending | Needs Python plugin discovery |
| **table-rendering/** | ❌ Pending | Needs `jn table` command |
| **code-lcov/** | ❌ Pending | Needs Python @code profiles |
| **adapter-merge/** | ❌ Pending | Needs DuckDB Python plugin |
| **genomoncology/** | 📋 Example | Shows syntax only (requires credentials) |

## Key Patterns

**Basic pipeline (✅ works):**
```bash
jn cat data.csv | jn filter '.revenue > 1000' | jn put output.json
```

**Shell commands (⚠️ requires jc):**
```bash
jn sh ps aux | jn filter '.cpu_percent > 10' | jn put high_cpu.json
```

**Format conversion (✅ for CSV/JSON):**
```bash
jn cat data.csv | jn put data.json   # CSV → JSON
```

**Pending features:**
- HTTP URLs: `jn cat "https://api.github.com/..."` (OpenDAL integration)
- Excel: `jn cat data.xlsx` (Python plugin discovery)
- Tables: `jn table` command (not yet in Zig)

For detailed examples, see the scripts in each demo directory.
