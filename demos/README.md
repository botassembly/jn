# JN Demos

Run these demos to see JN's ETL capabilities in action. Each demo has a well-commented script showing how to use JN.

## Prerequisites

Before running demos, build and activate JN:

```bash
cd ..
make build
source dist/activate.sh
```

## Quick Start

```bash
cd csv-filtering && ./run_examples.sh     # Core ETL operations
cd join && ./run_examples.sh              # Stream enrichment via hash join
cd json-editing && ./run_examples.sh      # Surgical JSON editing with jn-edit
cd zq-functions && ./run_examples.sh      # ZQ built-in functions showcase
cd todo && ./run_examples.sh              # Task management tool demo
```

## Available Demos

| Demo | Status | Description |
|------|--------|-------------|
| **csv-filtering/** | ✅ Working | Read CSV, filter with ZQ, convert formats |
| **join/** | ✅ Working | Stream enrichment via hash join |
| **json-editing/** | ✅ Working | Surgical JSON editing with jn-edit tool |
| **zq-functions/** | ✅ Working | ZQ built-in functions (generators, transforms, time) |
| **todo/** | ✅ Working | Task management with BEADS-inspired dependencies |
| **shell-commands/** | ✅ Working | Convert shell output to NDJSON (requires `jc`) |
| **http-api/** | ✅ Working | Fetch from REST APIs via curl |
| **glob/** | ✅ Working | Process multiple files with glob patterns |
| **xlsx-files/** | ✅ Working | Read/write Excel files (Python plugin) |
| **table-rendering/** | ✅ Working | Pretty-print NDJSON as ASCII/markdown tables |
| **code-lcov/** | ✅ Working | Analyze code files via @code profiles |
| **adapter-merge/** | ✅ Working | DuckDB profiles + merge for data comparison |
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

**JSON editing (jn-edit):**
```bash
echo '{"name":"Alice"}' | jn-edit .age:=30      # Add number field
echo '{"x":1}' | jn-edit .y:=2 .z:=3            # Multiple edits
echo '{"a":[1]}' | jn-edit --append .a 2       # Append to array
```

**Task management (todo):**
```bash
todo add "Fix bug" -p high                      # Add task with priority (returns XID)
todo blocks abc12 def34                         # Task abc12 blocks def34 (partial XIDs)
todo ready                                      # Show actionable tasks
todo done abc12                                 # Mark as done (partial XID matching)
todo stats                                      # Statistics dashboard
```

**ZQ functions:**
```bash
echo '{}' | zq 'xid'                            # Generate XID
echo '{}' | zq 'now'                            # Current timestamp
echo '{"ts":1734300000}' | zq '.ts | ago'       # Human-friendly relative time
echo '{"id":"abc..."}' | zq '.id | xid_time'    # Extract timestamp from XID
```

For detailed examples, see the scripts in each demo directory.
