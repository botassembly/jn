# XLSX Format Plugin

## What
Read Excel spreadsheet files (.xlsx) and convert to NDJSON for pipeline processing.

## Why
Excel is ubiquitous in business. Enable processing spreadsheet data with standard JN pipelines and filters.

## Key Features
- Read XLSX files (first row = headers, rows = records)
- Multiple sheet support (default first sheet, select by name/index)
- Data type preservation (numbers, dates, text, booleans)
- Streaming (row-by-row, constant memory)
- Works with remote URLs (combine with HTTP plugin)

## Dependencies
- `openpyxl` (pure Python, most popular XLSX library)

## Examples
```bash
# Local file
jn cat data.xlsx | jn put output.json

# Remote file
jn cat https://example.com/sales.xlsx | jn filter '.revenue > 1000' | jn put filtered.csv

# Specific sheet
jn cat workbook.xlsx --sheet "Q4 Sales" | jn jtbl
```

## Out of Scope
- Writing XLSX (add later)
- Formula evaluation (read values only)
- Formatting/charts (data only)
