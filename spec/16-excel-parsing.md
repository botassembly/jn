# Excel Parsing Modes

> **Purpose**: Deep dive design for parsing Excel files (xlsx/xlsm) with multiple modes to handle both well-structured and messy spreadsheets.

---

## Problem Statement

Excel files in the wild vary dramatically in structure:

1. **Clean tables**: First row is headers, data below, single sheet - works like CSV
2. **Title rows**: Report title in row 1, headers in row 3, data below
3. **Multiple tables**: Several independent tables on one sheet
4. **Sparse data**: Random cells scattered with notes, labels, actual data
5. **Merged cells**: Headers or data spanning multiple rows/columns
6. **Formulas**: Computed values vs formula text
7. **Multiple sheets**: Each sheet may have different structure

The current plugin assumes Case 1. This spec designs modes to handle all cases.

---

## Excel Terminology

Before diving into modes, here's the terminology we'll use (matching Excel/LLM familiarity):

| Term | Example | Description |
|------|---------|-------------|
| **Cell Reference** | `A1`, `B5` | Single cell address (A1 notation) |
| **Range** | `A1:D10` | Rectangular region of cells |
| **Sheet Reference** | `Sheet1!A1:D10` | Range qualified with sheet name |
| **Row** | `1`, `5` | Entire row (1-indexed) |
| **Column** | `A`, `D` | Entire column (letter-based) |
| **Merged Cells** | `B5:D5` | Multiple cells displayed as one |

We use **A1 notation** (not R1C1) because it's the Excel default and what LLMs are trained on.

---

## Mode Overview

| Mode | Purpose | Output |
|------|---------|--------|
| **simple** | Assume clean CSV-like structure | NDJSON records with field names from row 1 |
| **stats** | Inspect workbook structure | NDJSON with sheet/dimension/merge metadata |
| **raw** | Output every cell with position | NDJSON with row, col, value, type, merge info |
| **table** | Extract specific region as table | NDJSON records from defined region |

```
┌─────────────────────────────────────────────────────────────────┐
│                         Mode Selection                          │
├─────────────────────────────────────────────────────────────────┤
│  Know structure? ──yes──> simple (fast, assumes clean table)    │
│       │                                                         │
│       no                                                        │
│       │                                                         │
│       v                                                         │
│  Need overview? ──yes──> stats (sheets, dimensions, merges)     │
│       │                                                         │
│       no                                                        │
│       │                                                         │
│       v                                                         │
│  Complex layout? ──yes──> raw (cell-level, agent-friendly)      │
│       │                                                         │
│       no (know the region)                                      │
│       │                                                         │
│       v                                                         │
│  table (extract specific range with config)                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Mode 1: Simple (Default)

**Purpose**: Treat Excel like CSV. Fast path for well-structured files.

### Behavior

1. Select sheet (default: first sheet, or `--sheet=<name|index>`)
2. Skip N rows if specified (`--skip-rows=N`)
3. Row 1 (after skip) = headers
4. Remaining rows = data records
5. Output: NDJSON with headers as field names

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--sheet` | `0` | Sheet name or 0-based index |
| `--skip-rows` | `0` | Rows to skip before header |

### Output Format

```json
{"Name": "Alice", "Age": 30, "City": "NYC"}
{"Name": "Bob", "Age": 25, "City": "LA"}
```

### Edge Cases

- **Empty header cell**: Named `Column_N` (1-indexed)
- **Merged cells in data**: Value from merge origin, null for other cells
- **Formulas**: Computed value if available, else formula text
- **Date/time**: ISO 8601 format

### CLI Example

```bash
jn cat data.xlsx                           # Simple mode, sheet 0
jn cat 'data.xlsx?sheet=Sales'             # Specific sheet by name
jn cat 'data.xlsx?sheet=2&skip_rows=3'     # Sheet index 2, skip 3 rows
```

---

## Mode 2: Stats

**Purpose**: Inspect workbook structure before deciding how to parse.

### Behavior

1. Scan all sheets
2. For each sheet: dimensions, merged cell ranges, named tables
3. Output: One NDJSON record per sheet

### Output Format

```json
{
  "sheet": "Sheet1",
  "index": 0,
  "dimensions": "A1:G25",
  "rows": 25,
  "cols": 7,
  "min_row": 1,
  "max_row": 25,
  "min_col": 1,
  "max_col": 7,
  "merged_ranges": ["B5:D5", "A7:A9"],
  "named_tables": [
    {"name": "SalesData", "range": "A1:D10"}
  ],
  "first_row": ["Name", "Q1", "Q2", "Total", null, null, null],
  "first_col": ["Name", "Alice", "Bob", "Charlie", null, ...]
}
```

### Fields

| Field | Description |
|-------|-------------|
| `sheet` | Sheet name |
| `index` | 0-based sheet index |
| `dimensions` | Data range (Excel's UsedRange) |
| `rows`, `cols` | Max row/column with data |
| `merged_ranges` | List of merged cell ranges |
| `named_tables` | Excel Table objects (if any) |
| `first_row` | Values from row 1 (helps identify headers) |
| `first_col` | Values from column A (helps identify row labels) |

### CLI Example

```bash
jn cat 'data.xlsx?mode=stats'              # Stats for all sheets
jn cat 'data.xlsx?mode=stats' | jq '.sheet'  # Just sheet names
```

### Use Case: LLM Workflow

```bash
# Step 1: Get stats
stats=$(jn cat 'messy.xlsx?mode=stats')

# Step 2: LLM analyzes stats, decides:
#   - Sheet "Report" has header in row 3
#   - Data range is B3:F50

# Step 3: Extract with table mode
jn cat 'messy.xlsx?mode=table&sheet=Report&range=B3:F50&header_row=3'
```

---

## Mode 3: Raw

**Purpose**: Output every non-empty cell with full metadata. No assumptions about structure.

### Behavior

1. Select sheet(s) (default: all sheets, or `--sheet=<name>`)
2. Iterate all non-empty cells
3. Output: One NDJSON record per cell

### Output Format

```json
{"sheet": "Sheet1", "row": 1, "col": 1, "ref": "A1", "value": "Name", "type": "s"}
{"sheet": "Sheet1", "row": 1, "col": 2, "ref": "B1", "value": "Age", "type": "s"}
{"sheet": "Sheet1", "row": 2, "col": 1, "ref": "A2", "value": "Alice", "type": "s"}
{"sheet": "Sheet1", "row": 2, "col": 2, "ref": "B2", "value": 30, "type": "n"}
{"sheet": "Sheet1", "row": 3, "col": 1, "ref": "A3", "value": "=SUM(B2:B10)", "type": "f", "computed": 255}
{"sheet": "Sheet1", "row": 5, "col": 2, "ref": "B5", "value": "Merged", "type": "s", "merge": "B5:D5", "merge_origin": true}
{"sheet": "Sheet1", "row": 5, "col": 3, "ref": "C5", "value": null, "type": "n", "merge": "B5:D5", "merge_origin": false}
```

### Fields

| Field | Description |
|-------|-------------|
| `sheet` | Sheet name |
| `row` | 1-based row number |
| `col` | 1-based column number |
| `ref` | A1-style cell reference |
| `value` | Cell value (or formula if type=f) |
| `type` | `s`=string, `n`=number, `f`=formula, `b`=boolean, `d`=date |
| `computed` | (formulas only) Computed value if available |
| `merge` | (merged cells) The merge range this cell belongs to |
| `merge_origin` | (merged cells) True if this is the top-left cell |

### Range Selector

Raw mode supports an optional range selector to limit output:

```bash
jn cat 'data.xlsx?mode=raw'                    # All cells, all sheets
jn cat 'data.xlsx?mode=raw&sheet=Sales'        # All cells in Sales sheet
jn cat 'data.xlsx?mode=raw&range=A1:D10'       # Cells in range (sheet 0)
jn cat 'data.xlsx?mode=raw&range=Sales!A:A'    # Column A of Sales sheet
jn cat 'data.xlsx?mode=raw&range=1:1'          # Row 1 of all sheets
```

### Range Syntax

| Syntax | Meaning |
|--------|---------|
| `A1:D10` | Rectangular range |
| `A:D` | Columns A through D (all rows) |
| `1:5` | Rows 1 through 5 (all columns) |
| `A1` | Single cell |
| `Sheet1!A1:D10` | Range in specific sheet |

### Use Case: Agent Table Detection

```python
# Agent receives raw cell data
cells = run("jn cat 'messy.xlsx?mode=raw'")

# Find connected regions of non-empty cells
regions = detect_regions(cells)

# For each region, check if row 1 looks like headers
for region in regions:
    headers = [c for c in cells if c['row'] == region.min_row]
    if all(c['type'] == 's' for c in headers):
        # Likely a table with headers
        extract_table(region)
```

---

## Mode 4: Table

**Purpose**: Extract a specific region as a table with explicit configuration.

### Behavior

1. Select sheet
2. Define data region (range)
3. Specify header location
4. Handle merged cells according to strategy
5. Output: NDJSON records

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--sheet` | `0` | Sheet name or index |
| `--range` | (full sheet) | Data range in A1 notation |
| `--header-row` | `1` (relative to range) | Row containing headers |
| `--header-col` | (none) | Column containing row labels (for transposed data) |
| `--merge-strategy` | `origin` | How to handle merged cells |
| `--skip-empty` | `true` | Skip completely empty rows |

### Header Modes

**Row headers (default)**:
```
    A       B       C
1   Name    Age     City
2   Alice   30      NYC
3   Bob     25      LA
```

Output:
```json
{"Name": "Alice", "Age": 30, "City": "NYC"}
{"Name": "Bob", "Age": 25, "City": "LA"}
```

**Column headers** (`--header-col=A`):
```
    A       B       C
1   Name    Alice   Bob
2   Age     30      25
3   City    NYC     LA
```

Output:
```json
{"Name": "Alice", "Age": 30, "City": "NYC"}
{"Name": "Bob", "Age": 25, "City": "LA"}
```

### Merge Strategies

| Strategy | Behavior |
|----------|----------|
| `origin` | Value from merge origin cell, null for others |
| `fill` | Fill all cells in merge with origin value |
| `expand` | Add `_merge` field with range info |

**Example with `fill`**:
```
Merged B1:D1 = "Q1 2024"
    A       B       C       D
1   Region  Q1 2024 (merged across B-D)
2   North   100     200     300
```

With `--merge-strategy=fill`:
```json
{"Region": "North", "Q1 2024": 100, "Q1 2024": 200, "Q1 2024": 300}
```

This creates duplicate keys - not ideal. Better to use `expand`:
```json
{"Region": "North", "Q1 2024": 100, "Q1 2024_1": 200, "Q1 2024_2": 300, "_merge_info": {"Q1 2024": "B1:D1"}}
```

### CLI Examples

```bash
# Basic table extraction
jn cat 'report.xlsx?mode=table&range=B3:F20&header_row=1'

# Transposed data (headers in column A)
jn cat 'report.xlsx?mode=table&range=A1:D5&header_col=A'

# Skip title rows, headers in row 3 of range
jn cat 'report.xlsx?mode=table&range=A3:G100&header_row=1'

# Handle merged headers by filling
jn cat 'report.xlsx?mode=table&merge_strategy=fill'
```

---

## Formula Handling

Formulas present a choice: return the formula text or the computed value?

### Options

| Option | Value | Description |
|--------|-------|-------------|
| `--formulas` | `computed` (default) | Return computed value if available |
| `--formulas` | `text` | Return formula text (e.g., `=SUM(A1:A10)`) |
| `--formulas` | `both` | Return object with both |

### Computed Value Limitation

**Important**: openpyxl cannot evaluate formulas. It can only read cached values that Excel computed when the file was last saved. If a file was:
- Created by openpyxl (no cached values)
- Modified but not opened in Excel
- Contains volatile functions

Then computed values may be `null`.

### Output Examples

**`--formulas=computed`** (default):
```json
{"Total": 300}
```

**`--formulas=text`**:
```json
{"Total": "=SUM(B2:B10)"}
```

**`--formulas=both`**:
```json
{"Total": {"formula": "=SUM(B2:B10)", "computed": 300}}
```

---

## Complete CLI Syntax

```
xlsx --mode={simple|stats|raw|table} [options]

Simple mode options:
  --sheet=<name|index>     Sheet to read (default: 0)
  --skip-rows=<n>          Skip rows before header (default: 0)
  --formulas=<computed|text|both>

Stats mode options:
  (none - always returns all sheets)

Raw mode options:
  --sheet=<name|index>     Sheet to read (default: all)
  --range=<A1:B2>          Cell range to output (default: all)
  --formulas=<computed|text|both>

Table mode options:
  --sheet=<name|index>     Sheet to read (default: 0)
  --range=<A1:B2>          Data range (default: full sheet)
  --header-row=<n>         Header row (1-indexed within range, default: 1)
  --header-col=<A>         Header column for transposed data
  --merge-strategy=<origin|fill|expand>
  --skip-empty=<true|false>
  --formulas=<computed|text|both>
```

---

## Query String Mapping

For `jn cat` integration, options map to query parameters:

```bash
jn cat 'file.xlsx?mode=raw&range=A1:D10'
jn cat 'file.xlsx?mode=table&sheet=Sales&header_row=3'
jn cat 'file.xlsx?mode=stats'
jn cat 'file.xlsx?sheet=2&skip_rows=2'  # Simple mode (default)
```

Parameter names use underscores in query strings:
- `header_row` → `--header-row`
- `skip_rows` → `--skip-rows`
- `merge_strategy` → `--merge-strategy`

---

## Implementation Notes

### openpyxl Capabilities

| Feature | API |
|---------|-----|
| Sheet names | `wb.sheetnames` |
| Sheet by name | `wb[name]` |
| Sheet by index | `wb[wb.sheetnames[i]]` |
| Dimensions | `ws.dimensions`, `ws.max_row`, `ws.max_column` |
| Cell value | `cell.value` |
| Cell type | `cell.data_type` (s, n, f, b, d) |
| Formula text | `cell.value` when `data_type='f'` |
| Computed value | Load with `data_only=True` |
| Merged ranges | `ws.merged_cells.ranges` |
| Check if merged | `cell.coordinate in merged_range` |
| Named tables | `ws.tables` |
| Range access | `ws['A1:D10']` |

### Performance Considerations

- **read_only mode**: Use `load_workbook(read_only=True)` for large files
- **data_only mode**: Separate load to get computed values
- **Streaming**: openpyxl supports row-by-row iteration

### Error Handling

| Error | Behavior |
|-------|----------|
| Sheet not found | Exit with error listing available sheets |
| Invalid range | Exit with error, suggest valid range |
| Empty sheet | Output nothing (not an error) |
| Corrupt file | Exit with openpyxl error |

---

## Examples: LLM Workflow

### Scenario: Unknown Excel File

```bash
# Step 1: Get structure overview
$ jn cat 'mystery.xlsx?mode=stats'
{"sheet": "Summary", "index": 0, "rows": 5, "cols": 3, "merged_ranges": [], "first_row": ["Report", null, null]}
{"sheet": "Data", "index": 1, "rows": 150, "cols": 8, "merged_ranges": ["A1:H1"], "first_row": ["Sales Report Q4 2024", ...]}
{"sheet": "Notes", "index": 2, "rows": 20, "cols": 2, "first_row": ["Date", "Note"]}

# LLM analysis:
# - Summary: Small, probably metadata
# - Data: Large, merged header row, actual data likely starts row 2
# - Notes: Simple two-column table

# Step 2: Extract Data sheet, skipping merged header
$ jn cat 'mystery.xlsx?mode=table&sheet=Data&range=A2:H150'
{"Region": "North", "Product": "Widget", ...}
```

### Scenario: Messy Spreadsheet with Multiple Tables

```bash
# Step 1: Raw dump to find tables
$ jn cat 'chaos.xlsx?mode=raw' > cells.jsonl

# Step 2: LLM/agent detects regions:
# - A1:A1 (single cell "Title")
# - C5:D6 (2x2 table)
# - B15:C16 (2x2 table)

# Step 3: Extract each table
$ jn cat 'chaos.xlsx?mode=table&range=C5:D6'
{"Header1": "data1", "Header2": "data2"}

$ jn cat 'chaos.xlsx?mode=table&range=B15:C16'
{"Table2_Col1": "val1", "Table2_Col2": "val2"}
```

---

## Migration from Current Plugin

### Current Behavior

```python
# Current xlsx plugin
--mode=read   → Simple mode (row 1 = headers)
--mode=write  → NDJSON to xlsx
--sheet=N     → Select sheet
--skip-rows=N → Skip before headers
```

### New Behavior

```python
# New modes - backwards compatible
--mode=read        → Alias for --mode=simple (default)
--mode=simple      → Row 1 headers, CSV-like
--mode=stats       → Workbook metadata
--mode=raw         → Cell-by-cell output
--mode=table       → Explicit region extraction
--mode=write       → NDJSON to xlsx (unchanged)
```

Existing `jn cat file.xlsx` continues to work unchanged.

---

## Open Questions

1. **Multi-sheet raw mode**: Output all sheets, or require explicit `--sheet`?
   - Proposal: Default to all sheets, with sheet name in each record

2. **Named ranges**: Excel supports named ranges like `SalesData`. Support as range selector?
   - Proposal: Yes, `--range=SalesData` should work

3. **Hidden sheets/rows/columns**: Include or skip?
   - Proposal: Include by default, add `--skip-hidden` option

4. **Comments**: Cell comments are separate from values. Include in raw mode?
   - Proposal: Yes, add `comment` field when present

5. **Number formats**: Currency, percentage, date formats. Expose?
   - Proposal: Add `format` field in raw mode, apply formatting in simple/table modes

---

## References

- [openpyxl documentation](https://openpyxl.readthedocs.io/)
- [tidyxl (R package)](https://github.com/nacnudus/tidyxl) - Raw cell approach inspiration
- [TableSense (Microsoft Research)](https://www.microsoft.com/en-us/research/uploads/prod/2019/01/TableSense_AAAI19.pdf) - ML table detection
- [A1 Notation (Microsoft)](https://learn.microsoft.com/en-us/office/vba/excel/concepts/cells-and-ranges/refer-to-cells-and-ranges-by-using-a1-notation)
- [Practical Business Python](https://pbpython.com/pandas-excel-range.html) - Handling messy Excel
