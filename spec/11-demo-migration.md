# Demo Migration Strategy

> **Purpose**: How to migrate existing demos to the Zig-based architecture.

---

## Migration Goal

**Functional equivalence**: All demos should work identically after migration. The user-facing commands (`jn cat`, `jn filter`, `jn put`, etc.) remain the same. Only the underlying implementation changes.

---

## Current Demos Inventory

| Demo | Purpose | Migration Status |
|------|---------|------------------|
| `csv-filtering/` | Core ETL: read CSV, filter, convert formats | Works as-is |
| `http-api/` | Fetch from REST APIs, transform responses | Works as-is |
| `join/` | Stream enrichment via hash join | Works as-is |
| `glob/` | Process multiple files with glob patterns | Works as-is |
| `shell-commands/` | Convert shell output to NDJSON via `jc` | Python plugin (stays) |
| `table-rendering/` | Pretty-print NDJSON as ASCII tables | Works as-is |
| `xlsx-files/` | Read/write Excel files | Python plugin (stays) |
| `code-lcov/` | Analyze pytest coverage reports | Works as-is |
| `adapter-merge/` | Profile-based data merging | Works as-is |
| `genomoncology/` | Real-world HTTP profile example | Works as-is |

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

**Status**: Works as-is

Core demo showcasing:
- `jn cat` reading CSV to NDJSON
- `jn filter` with ZQ expressions
- `jn put` writing to various formats
- `jn head` for early termination

No changes needed. This is the golden path demo.

### http-api/

**Status**: Works as-is

Demonstrates:
- HTTP fetching with format hints (`~json`)
- Response transformation
- API data extraction

The Zig HTTP plugin replaces Python HTTP, but the CLI interface is identical.

### join/

**Status**: Works as-is

Demonstrates:
- Hash join (`jn join`)
- Key mapping (`--left-key`, `--right-key`)
- Target embedding (`--target`)
- Aggregation (`--agg`)

Reference: [09-joining-operations.md](09-joining-operations.md)

### glob/

**Status**: Works as-is

Demonstrates:
- Glob pattern expansion (`jn cat "*.csv"`)
- Multi-file processing
- Source tagging

### shell-commands/

**Status**: Python plugin (stays in Python)

Demonstrates:
- Shell command execution (`jn sh`)
- `jc` integration for parsing
- NDJSON output from CLI tools

This uses Python's `jc` library. The shell plugin discovery and invocation is handled by the Zig orchestrator, but the plugin itself remains Python.

**Reference**: [10-python-plugins.md](10-python-plugins.md)

### table-rendering/

**Status**: Works as-is

Demonstrates:
- Pretty printing (`jn table`)
- Table formats (grid, github, fancy_grid)
- Column width handling

The Zig `jn-table` tool replaces Python's tabulate-based implementation.

### xlsx-files/

**Status**: Python plugin (stays in Python)

Demonstrates:
- Excel file reading
- Excel file writing
- Format conversion

The XLSX plugin requires `openpyxl` and stays in Python. Invocation is unchanged.

**Reference**: [10-python-plugins.md](10-python-plugins.md)

### code-lcov/

**Status**: Works as-is

Demonstrates:
- Coverage report analysis
- ZQ profile usage
- Data aggregation

### adapter-merge/

**Status**: Works as-is

Demonstrates:
- Profile-based configuration
- Multi-source merging
- DuckDB integration (Python plugin)

### genomoncology/

**Status**: Works as-is (requires credentials)

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
