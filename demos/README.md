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
cd csv-filtering && ./run_examples.sh     # Core ETL operations
cd join && ./run_examples.sh              # Stream enrichment via hash join
cd table-rendering && ./run_examples.sh   # Pretty-print NDJSON as tables
cd xlsx-files && ./run_examples.sh        # Read/write Excel files
```

## Available Demos

| Demo | Status | Description |
|------|--------|-------------|
| **csv-filtering/** | ✅ Working | Read CSV, filter with ZQ, convert formats |
| **join/** | ✅ Working | Stream enrichment via hash join |
| **shell-commands/** | ✅ Working | Convert shell output to NDJSON (requires `jc`) |
| **http-api/** | ✅ Working | Fetch from REST APIs via curl |
| **glob/** | ✅ Working | Process multiple files with glob patterns |
| **xlsx-files/** | ✅ Working | Read/write Excel files (Python plugin) |
| **table-rendering/** | ✅ Working | Pretty-print NDJSON as ASCII/markdown tables |
| **code-lcov/** | ✅ Working | Analyze code files via @code profiles |
| **adapter-merge/** | ✅ Working | DuckDB profiles + merge for data comparison |
| **markdown-skills/** | ✅ Working | Parse markdown with frontmatter (Python plugin) |
| **genomoncology/** | 📋 Example | Shows syntax only (requires credentials) |

## Key Patterns

**Basic pipeline:**
```bash
jn cat data.csv | jn filter '.revenue > 1000' | jn put output.json
```

**Shell commands (requires jc):**
```bash
jn sh ps aux | jn filter '.cpu_percent > 10' | jn put high_cpu.json
```

**Format conversion:**
```bash
jn cat data.csv | jn put data.json      # CSV → JSON
jn cat data.xlsx | jn put data.csv      # Excel → CSV
```

**HTTP fetching:**
```bash
jn cat "https://api.github.com/users/octocat~json" | jn put user.json
```

**Table rendering:**
```bash
jn cat data.csv | jn table --tablefmt github   # Markdown table
```

**Profile-based queries:**
```bash
jn cat @genie/treatment                         # DuckDB query
jn cat '@genie/treatment?regimen=FOLFOX'        # With parameters
```

For detailed examples, see the scripts in each demo directory.

## Writing Demos

See [good-demo-bad-demo-guidelines.md](./good-demo-bad-demo-guidelines.md) for best practices.
