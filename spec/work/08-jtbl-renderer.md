# JTBL Renderer Plugin

## What
Render NDJSON data as formatted tables for human-readable terminal output. Uses JTBL library (from JC project creator).

## Why
Data exploration and debugging requires visual inspection. Tables are easier to read than raw JSON.

## Key Features
- Multiple formats (simple, grid, markdown, HTML, LaTeX)
- Auto-detect terminal width
- Support for various table styles (plain, fancy_grid, github markdown, etc.)

## Dependencies
- `jtbl` (JSON table renderer by Kelly Brazil)

## Examples
```bash
# Basic rendering
jn cat users.json | jn jtbl

# With format
jn cat @mydb/sales.sql --limit 10 | jn jtbl --format grid

# Markdown export
jn cat data.csv | jn jtbl --format markdown > report.md
```

## Important
- **Must be last in pipeline** - outputs formatted text, not NDJSON
- **Loads all rows in memory** - use `jn head` to limit large datasets
- Cannot pipe jtbl output to other jn commands

## Usage Patterns
```bash
# Good - filter first, then render
jn cat data.json | jn filter '.active == true' | jn jtbl  ✓

# Bad - can't pipe jtbl output
jn cat data.json | jn jtbl | jn filter '...'  ❌
```
