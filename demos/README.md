# JN Demos

Run these demos to see JN's ETL capabilities in action. Each demo has a well-commented script showing how to use JN.

## Quick Start

```bash
cd csv-filtering && ./run_examples.sh     # Core ETL operations
cd http-api && ./run_examples.sh          # Fetch from REST APIs
cd shell-commands && ./run_examples.sh    # Convert shell output to NDJSON
cd xlsx-files && ./run_examples.sh        # Work with Excel files
cd coverage-analysis && ./run_examples.sh # Analyze pytest coverage reports
```

## Available Demos

1. **csv-filtering/** - Read CSV, filter with jq, convert formats, aggregate data
2. **http-api/** - Fetch from GitHub/REST APIs, transform responses, save locally
3. **shell-commands/** - Convert ls/ps/df/env output to NDJSON (requires `jc`)
4. **xlsx-files/** - Read/write Excel files, filter spreadsheets (requires `openpyxl`)
5. **coverage-analysis/** - Analyze pytest coverage with reusable JQ profiles
6. **mcp/** - Model Context Protocol integration (documentation)
7. **genomoncology/** - Real-world HTTP profile example (requires credentials)

## Key Patterns

**Basic pipeline:**
```bash
jn cat data.csv | jn filter '.revenue > 1000' | jn put output.json
```

**Fetch from API:**
```bash
jn cat "https://api.github.com/users/octocat~json" | jn put user.json
```

**Shell commands:**
```bash
jn sh ps aux | jn filter '.cpu_percent > 10' | jn put high_cpu.json
```

**Format conversion:**
```bash
jn cat data.xlsx | jn put data.csv   # Excel → CSV
jn cat data.csv | jn put data.json   # CSV → JSON
```

For detailed examples, see the scripts in each demo directory. All scripts include comprehensive comments explaining each step.
