# JTBL Renderer Plugin

## Overview
Implement a filter plugin that renders NDJSON data as formatted tables for human-readable output. Uses JTBL (JSON Table) from the JC project creator to display data in terminal-friendly formats.

## Goals
- Convert NDJSON to formatted ASCII tables
- Support multiple output formats (plain, grid, markdown, etc.)
- Auto-detect terminal width for optimal display
- Handle wide tables (truncate or wrap)
- Colorize output for better readability (optional)

## Resources
**JTBL Project:** https://github.com/kellyjonbrazil/jtbl
- Created by Kelly Brazil (same author as JC project)
- Pure Python, minimal dependencies
- Multiple table formats via `tabulate` library
- Designed specifically for JSON → table conversion

**Documentation:** https://github.com/kellyjonbrazil/jtbl#readme

## Dependencies
**Python packages:**
- `jtbl` - JSON table renderer

Add to PEP 723 dependencies:
```toml
dependencies = ["jtbl>=1.5.0"]
```

This transitively includes `tabulate` (table formatting library).

## Technical Approach
- Implement `filters()` function to convert NDJSON to table
- Pattern matching: None (invoked by name, not pattern)
- Read all input records (tables need all rows for column width)
- Convert NDJSON to list of dicts
- Call jtbl library to format table
- Output to stdout (not NDJSON - terminal output only)
- Support format selection via `--format` flag

## Usage Examples

```bash
# Basic table rendering
jn cat users.json | jn jtbl

# With specific format
jn cat users.json | jn jtbl --format grid

# In pipeline
jn cat @mydb/active-users.sql --limit 10 | jn jtbl

# From HTTP API
jn cat @restful-api-dev/objects | jn filter '.data.year > 2020' | jn jtbl

# Markdown format (for documentation)
jn cat sales.csv | jn jtbl --format markdown > report.md

# Simple format (plain, no borders)
jn cat data.json | jn jtbl --format simple
```

## Table Formats
Supported via `--format` flag (from tabulate):
- `simple` (default) - Plain columns, no borders
- `plain` - Minimal, space-separated
- `grid` - Full grid with borders
- `fancy_grid` - Unicode box-drawing characters
- `pipe` - Markdown-style pipes
- `github` - GitHub-flavored markdown
- `html` - HTML table
- `latex` - LaTeX table

## Out of Scope
- Interactive table navigation (paging, sorting) - use `less` or dedicated tool
- Sparklines or data visualization - dedicated plugin later
- Exporting to image (PNG, SVG) - out of scope
- Column reordering - use `jn filter` to select columns
- Cell formatting (colors per cell) - basic only
- Pivot tables - use SQL or dedicated tool
- Aggregation (sum, avg) - use `jn filter` with jq
- Filtering within table - use `jn filter` before rendering
- Excel-style formulas - out of scope

## Implementation Notes
**JTBL expects:**
- Array of objects (list of dicts)
- Consistent keys across objects
- Handles missing keys gracefully

**Non-NDJSON Output:**
This plugin is special - it doesn't output NDJSON! It outputs formatted text.
- Cannot be piped to other JN commands
- Must be last stage in pipeline
- Used for human viewing, not further processing

**Memory Usage:**
Tables require loading all rows (can't stream) to calculate column widths.
- Limit input with `jn head` before rendering
- Not suitable for huge datasets (>10K rows)

## Usage Patterns

```bash
# Bad - jtbl output isn't NDJSON
jn cat data.json | jn jtbl | jn filter '...'  ❌

# Good - filter first, then render
jn cat data.json | jn filter '.active == true' | jn jtbl  ✓

# Good - limit rows for large datasets
jn cat @mydb/users.sql | jn head -n 100 | jn jtbl  ✓

# Good - for viewing intermediate results
jn cat data.json | jn filter '.score > 90' | tee high-scores.json | jn jtbl  ✓
```

## Success Criteria
- Renders NDJSON as formatted tables
- Multiple format options work
- Auto-detects terminal width
- Handles missing values gracefully
- Clear error if input isn't valid JSON
- Works at end of pipelines
- Useful for debugging and data exploration

## Related: JC Project Vendoring
This is separate from vendoring JC shell plugins (ticket #09).
JTBL is a standalone tool we use as-is via dependency.
JC project provides shell command parsers we'll vendor and modify.
