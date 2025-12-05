# Demo Migration Strategy

> **Purpose**: How to migrate existing demos to the Zig-based architecture.

---

## Migration Goal

**Functional equivalence**: All demos should work identically after migration. The user-facing commands (`jn cat`, `jn filter`, `jn put`, etc.) remain the same. Only the underlying implementation changes.

---

## Current Demos Inventory

| Demo | Purpose | Status |
|------|---------|--------|
| `csv-filtering/` | Core ETL: read CSV, filter, convert formats | ✅ Working |
| `http-api/` | Fetch from REST APIs, transform responses | ✅ Working |
| `join/` | Stream enrichment via hash join | ✅ Working |
| `glob/` | Process multiple files with glob patterns | ✅ Working |
| `shell-commands/` | Convert shell output to NDJSON via `jc` | ✅ Working (requires `jc`) |
| `table-rendering/` | Pretty-print NDJSON as ASCII tables | ✅ Working |
| `xlsx-files/` | Read/write Excel files | ✅ Working (Python plugin) |
| `code-lcov/` | Analyze pytest coverage reports | ⚠️ Requires code_ profile |
| `adapter-merge/` | Profile-based data merging | ⚠️ Requires DuckDB setup |
| `genomoncology/` | Real-world HTTP profile example | 📋 Requires credentials |

---

## Why Demos Should "Just Work"

The migration preserves the CLI interface:

```bash
# These commands work identically before and after migration
jn cat data.csv | jn filter '.x > 10' | jn put output.json
jn cat https://api.github.com/users/octocat~json | jn put user.json
jn cat orders.csv | jn join customers.csv --on customer_id
```

**What changes**: The `jn` commands are now Zig binaries instead of Python wrappers.

**What stays the same**:
- Command syntax and arguments
- NDJSON streaming behavior
- Filter expressions (ZQ syntax)
- Address syntax (`file~format?params`)
- Profile references (`@namespace/name`)

---

## Demo-Specific Notes

### csv-filtering/

**Status**: ✅ Working

Core demo showcasing:
- `jn cat` reading CSV to NDJSON
- `jn filter` with ZQ expressions
- `jn put` writing to various formats
- `jn head` for early termination

Uses Zig CSV plugin. This is the golden path demo.

### http-api/

**Status**: ✅ Working

Demonstrates:
- HTTP fetching with format hints (`~json`)
- Response transformation
- API data extraction

Uses curl via jn-cat for HTTP URLs.

### join/

**Status**: ✅ Working

Demonstrates:
- Hash join (`jn join`)
- Key mapping (`--left-key`, `--right-key`)
- Target embedding (`--target`)
- Aggregation (`--agg`)

Reference: [09-joining-operations.md](09-joining-operations.md)

### glob/

**Status**: ✅ Working

Demonstrates:
- Glob pattern expansion (`jn cat "*.csv"`)
- Multi-file processing
- Source tagging

### shell-commands/

**Status**: ✅ Working (requires `jc`)

Demonstrates:
- Shell command execution (`jn sh`)
- `jc` integration for parsing
- NDJSON output from CLI tools

Uses jn-sh tool with optional `jc` for structured parsing.

**Reference**: [10-python-plugins.md](10-python-plugins.md)

### table-rendering/

**Status**: ✅ Working

Demonstrates:
- Pretty printing (`jn table`)
- Table formats (grid, github, fancy_grid)
- Column width handling

Uses Python's tabulate-based implementation via `table_.py` plugin.

### xlsx-files/

**Status**: ✅ Working (Python plugin)

Demonstrates:
- Excel file reading
- Excel file writing
- Format conversion

The XLSX plugin requires `openpyxl` and stays in Python. Invocation is unchanged.

**Reference**: [10-python-plugins.md](10-python-plugins.md)

### code-lcov/

**Status**: ⚠️ Requires code_ profile protocol

Demonstrates:
- Coverage report analysis
- ZQ profile usage
- Data aggregation

### adapter-merge/

**Status**: ⚠️ Requires DuckDB setup

Demonstrates:
- Profile-based configuration
- Multi-source merging
- DuckDB integration (Python plugin)

### genomoncology/

**Status**: 📋 Requires credentials

Demonstrates:
- Real-world HTTP profile
- API authentication via profiles
- Complex data extraction

---

## Python Plugins That Stay

These plugins remain in Python due to ecosystem dependencies:

| Plugin | Reason | Demo Usage |
|--------|--------|------------|
| `xlsx_.py` | Requires openpyxl | xlsx-files/ |
| `watch_shell.py` | Requires watchfiles | (no demo) |
| `gmail_.py` | Requires Google APIs | (no demo) |
| `mcp_.py` | Requires MCP SDK | (deleted demo) |
| `duckdb_.py` | Requires DuckDB bindings | adapter-merge/ |

**Reference**: [10-python-plugins.md](10-python-plugins.md)

---

## Migration Verification

### Per-Demo Checklist

For each demo:

1. **Run the demo script**: `./run_examples.sh`
2. **Verify output files**: Check that outputs match expected
3. **Check error handling**: Intentional errors should produce clear messages
4. **Verify streaming**: Large inputs should stream (not buffer)

### Regression Test

```bash
# Run all demos
cd demos && ./run_all.sh

# Check for failures
echo $?  # Should be 0
```

### Performance Verification

```bash
# Compare startup time (Zig should be <5ms)
time jn cat --help

# Compare memory usage (should be constant ~1MB)
/usr/bin/time -v jn cat large.csv | jn head -n 10
```

---

## Demo Updates Needed

### README Updates

Update `demos/README.md`:
- Remove MCP demo reference (deleted)
- Clarify which demos use Python plugins

### Script Updates

Minor updates may be needed:
- Remove `uv run --project` wrapper if Zig binaries are in PATH
- Update comments referencing Python implementation

### New Demos to Consider

After migration is complete:
- **Benchmark demo**: Show Zig vs Python performance
- **Backpressure demo**: Demonstrate early termination with large files

---

## See Also

- [03-users-guide.md](03-users-guide.md) - Command reference
- [09-joining-operations.md](09-joining-operations.md) - Join command details
- [10-python-plugins.md](10-python-plugins.md) - Python plugins that stay
