# JN Table Command Design

## Overview

The `jn table` command provides a clean, dedicated interface for rendering NDJSON data as formatted tables. It solves CLI ergonomics issues with the current `jn put -- "-~table"` approach and offers terminal-aware features.

## Motivation

### Current Problems

1. **Awkward Syntax**: The `jn put -- "-~table"` pattern requires a `--` separator because `-~` is parsed as an option flag by Click.

2. **Non-Discoverable**: Table rendering is hidden inside the `jn put` command's address syntax, not visible in `jn --help`.

3. **Option Friction**: Parameters require URL encoding: `?tablefmt=grid&maxcolwidths=30` instead of natural CLI options.

4. **Boolean Flag Bug**: `action="store_true"` flags don't work via URL parameters (affects `--showindex`).

### Why Tables Are Special

Tables are fundamentally different from other formats:

| Aspect | Data Formats (CSV, JSON) | Tables |
|--------|-------------------------|--------|
| Purpose | Data interchange | Human viewing |
| Output | Machine-readable | Terminal display |
| Pipeable | Yes | No (text breaks NDJSON) |
| Direction | Bidirectional | Write-only (display) |

Tables are **terminal endpoints**, not data interchange formats. They deserve dedicated treatment.

## Design

### Command Interface

```
Usage: jn table [OPTIONS]

  Render NDJSON as a formatted table.

  Reads NDJSON from stdin and outputs a formatted table to stdout.
  Tables are for human viewing - they cannot be piped to other jn commands.

Options:
  -f, --format TEXT     Table format style [default: grid]
                        Options: grid, simple, github, fancy_grid, pipe,
                        orgtbl, jira, presto, pretty, psql, rst, mediawiki,
                        html, latex, tsv, rounded_grid, heavy_grid, etc.
  -w, --width INT       Maximum column width (text wraps)
  --index               Show row index numbers
  --no-header           Hide header row
  --right TEXT          Right-align these columns (comma-separated)
  --center TEXT         Center these columns (comma-separated)
  -h, --help            Show this message and exit.

Examples:
  jn cat data.csv | jn table                    # Default grid format
  jn cat data.csv | jn table -f github          # GitHub markdown
  jn cat data.csv | jn table -f fancy_grid      # Unicode box drawing
  jn cat data.csv | jn table -w 40              # Wrap at 40 chars
  jn cat data.csv | jn table --index            # Show row numbers
  jn cat data.csv | jn filter '.active' | jn table
```

### Usage Comparison

**Before (awkward):**
```bash
jn cat data.csv | jn put -- "-~table"
jn cat data.csv | jn put -- "-~table.github"
jn cat data.csv | jn put -- "-~table?tablefmt=grid&maxcolwidths=30"
jn cat data.csv | jn put -- "-~table?showindex=true"  # BUG: Doesn't work!
```

**After (clean):**
```bash
jn cat data.csv | jn table
jn cat data.csv | jn table -f github
jn cat data.csv | jn table -f grid -w 30
jn cat data.csv | jn table --index
```

### Supported Formats

All formats from the `tabulate` library are supported:

| Format | Description | Use Case |
|--------|-------------|----------|
| `grid` | ASCII box drawing (default) | Terminal viewing |
| `simple` | Minimal, no borders | Clean output |
| `github` | GitHub-flavored markdown | Documentation |
| `pipe` | Standard markdown | Documentation |
| `fancy_grid` | Unicode box characters | Beautiful terminals |
| `psql` | PostgreSQL style | Database familiarity |
| `rst` | reStructuredText | Sphinx docs |
| `html` | HTML table | Web export |
| `latex` | LaTeX tabular | Academic papers |
| `tsv` | Tab-separated | Spreadsheet import |
| `jira` | Jira wiki markup | Issue tracking |
| `mediawiki` | MediaWiki markup | Wiki pages |

See `tabulate` documentation for the full list of 25+ formats.

## Implementation

### Architecture

```
jn table
    │
    ▼
┌─────────────────┐
│  Click Command  │  Parse options, validate
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Read stdin     │  Stream NDJSON records
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  tabulate()     │  Format as table
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Print stdout   │  Display to terminal
└─────────────────┘
```

### Code Location

`src/jn/cli/commands/table.py`

### Key Implementation Details

1. **Direct tabulate usage**: No subprocess - import tabulate directly for simplicity.

2. **Streaming input**: Read NDJSON line-by-line, collect into list for tabulate.

3. **SIGPIPE handling**: Gracefully handle broken pipes (e.g., `| head`).

4. **Error handling**: Clear messages for invalid JSON, missing columns.

### Integration

Register in `src/jn/cli/main.py`:

```python
from .commands.table import table
cli.add_command(table)
```

## Testing

### Test Cases

1. **Basic rendering**: Default grid format
2. **Format options**: All major formats (github, simple, fancy_grid, etc.)
3. **Column width**: `--width` option wraps text correctly
4. **Index display**: `--index` shows row numbers
5. **No header**: `--no-header` hides header row
6. **Empty input**: Graceful handling of empty stream
7. **Invalid JSON**: Clear error message
8. **Large datasets**: Memory efficient for reasonable sizes
9. **Unicode data**: Proper handling of non-ASCII characters
10. **Pipeline integration**: Works with `jn cat`, `jn filter`, etc.

### Test File

`tests/cli/test_table_command.py`

## Backward Compatibility

The existing `jn put -- "-~table"` syntax continues to work. The new `jn table` command is an additional, ergonomic interface to the same functionality.

## Future Enhancements

1. **Terminal width detection**: Auto-adjust column widths
2. **Colorization**: Highlight headers, alternate row colors
3. **Paging**: Built-in pager for large tables
4. **Column selection**: Show only specific columns
5. **Sorting**: Sort by column before display

## Related Documents

- `spec/wip/table-analysis.md` - Initial analysis and findings
- `spec/done/format-design.md` - Format plugin architecture
- `spec/done/addressability.md` - Universal addressing syntax
