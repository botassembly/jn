# Excel Source/Target Adapter

## Overview

Excel adapter for reading and writing Excel files in both legacy (.xls) and modern (.xlsx) formats. Designed for streaming row-based data extraction and tabular data export.

## Supported Formats

- **.xlsx** - Modern XML-based Excel format (Excel 2007+)
- **.xls** - Legacy binary Excel format (Excel 97-2003)

## Design Philosophy

**Source adapter priority**: Streaming row extraction with optional structure detection
**Target adapter priority**: Simple tabular output from NDJSON records

Unlike document structure parsers, Excel adapter treats spreadsheets as **data tables**, not hierarchical documents. Focus is on extracting/writing rectangular data efficiently.

## Libraries

### Reading
- **openpyxl** (for .xlsx): Mature, supports read_only mode for streaming, handles formulas and merged cells
- **xlrd** (for .xls): Legacy format support, read-only, battle-tested

### Writing
- **openpyxl** (for .xlsx): Can write workbooks, formulas, styles
- **xlsxwriter** (for .xlsx, alternative): Write-only, faster for large datasets

**Recommendation**: Use openpyxl for both reading and writing .xlsx (single dependency), xlrd for reading .xls only.

## Source Adapter: Excel → NDJSON

### Record Structure

**Simple row mode** (default):
```json
{"row": 1, "A": "Name", "B": "Age", "C": "City"}
{"row": 2, "A": "Alice", "B": 30, "C": "NYC"}
{"row": 3, "A": "Bob", "B": 25, "C": "SF"}
```

**Header mode** (`--header`):
```json
{"row": 2, "Name": "Alice", "Age": 30, "City": "NYC"}
{"row": 3, "Name": "Bob", "Age": 25, "City": "SF"}
```

**Multi-sheet mode** (`--all-sheets`):
```json
{"sheet": "Sales", "row": 1, "A": "Product", "B": "Revenue"}
{"sheet": "Sales", "row": 2, "A": "Widget", "B": 1000}
{"sheet": "Inventory", "row": 1, "A": "Item", "B": "Quantity"}
{"sheet": "Inventory", "row": 2, "A": "Gadget", "B": 50}
```

### CLI Options

```bash
# Basic usage
jn cat data.xlsx                    # First sheet, simple column names (A, B, C...)

# Header mode
jn cat data.xlsx --header           # First row as column names
jn cat data.xlsx --header-row 3     # Row 3 as column names

# Sheet selection
jn cat data.xlsx --sheet "Sales"    # Specific sheet by name
jn cat data.xlsx --sheet 2          # Sheet by index (1-based)
jn cat data.xlsx --all-sheets       # All sheets with sheet column

# Range selection
jn cat data.xlsx --range A1:D100    # Excel range notation
jn cat data.xlsx --skip-rows 5      # Skip first N rows
jn cat data.xlsx --max-rows 100     # Limit to N rows

# Value handling
jn cat data.xlsx --formulas         # Show formula text instead of calculated value
jn cat data.xlsx --no-empty-rows    # Skip rows where all cells are empty
jn cat data.xlsx --no-empty-cols    # Skip columns where all cells are empty

# Type handling
jn cat data.xlsx --strings-only     # Convert all values to strings
jn cat data.xlsx --dates-iso        # Format dates as ISO 8601 strings
```

### Streaming Strategy

**For .xlsx files**:
```python
from openpyxl import load_workbook

# Use read_only mode for streaming
wb = load_workbook(filename, read_only=True, data_only=True)
ws = wb.active

for row in ws.iter_rows(min_row=1, max_row=None, values_only=True):
    # Emit NDJSON record
    yield record
```

**Benefits**:
- Low memory footprint (doesn't load entire workbook)
- Can process millions of rows
- data_only=True gives calculated values, not formulas

**Limitations**:
- read_only mode can't access merged cell ranges accurately
- Can't detect tables (requires full parse)

### Type Mapping

Excel → JSON type conversion:

| Excel Type | JSON Type | Notes |
|------------|-----------|-------|
| Number | number | 42, 3.14 |
| String | string | "hello" |
| Boolean | boolean | true, false |
| Date/DateTime | string | ISO 8601: "2025-01-15T10:30:00" |
| Formula | number/string | Calculated value (default) or formula text (--formulas) |
| Blank | null | Empty cell → null |
| Error | string | "#DIV/0!", "#N/A", etc. |

### Edge Cases

**Merged cells**:
- In streaming mode: Only first cell has value, rest are null
- Add `--unmerge` flag to copy value to all cells in merge range (requires buffering)

**Multiple header rows**:
- `--header-row` takes single row only
- For complex headers, use `--range` to skip rows manually

**Hidden rows/columns**:
- Include by default
- Add `--skip-hidden` flag to filter (requires full parse)

**Protected sheets**:
- Read-only works fine
- Writing to protected sheets will error

**Large numbers**:
- Excel stores numbers as float64
- May lose precision for very large integers (>15 digits)
- Consider `--strings-only` for ID columns

### Example Workflows

**Extract sales data with headers**:
```bash
jn cat sales.xlsx --header --sheet "Q1 Sales" | jq '.[] | select(.Revenue > 1000)'
```

**Combine multiple sheets**:
```bash
jn cat report.xlsx --all-sheets | jq 'select(.sheet == "Sales" or .sheet == "Marketing")'
```

**Get first 10 rows for inspection**:
```bash
jn head -n 10 data.xlsx --header
```

**Convert to CSV**:
```bash
jn cat data.xlsx --header | jq -r '[.Name, .Age, .City] | @csv'
```

## Target Adapter: NDJSON → Excel

### Input Requirements

NDJSON records with consistent keys:
```json
{"Name": "Alice", "Age": 30, "City": "NYC"}
{"Name": "Bob", "Age": 25, "City": "SF"}
```

### CLI Options

```bash
# Basic usage
jn cat data.csv | jn put output.xlsx

# Options
jn put output.xlsx \
  --sheet "Results" \              # Sheet name (default: "Sheet1")
  --header \                        # Include header row with column names
  --overwrite                       # Overwrite existing file (default: error if exists)

# Force format if extension is ambiguous
jn put output.txt --format excel   # Write Excel to .txt file (unusual)
```

### Writing Strategy

**Buffering required**: Target adapters must collect all records to write workbook.

```python
from openpyxl import Workbook

# Collect all records
records = list(ndjson_stream)

# Create workbook
wb = Workbook()
ws = wb.active
ws.title = sheet_name

# Write header
if header:
    ws.append(list(records[0].keys()))

# Write rows
for record in records:
    ws.append(list(record.values()))

wb.save(filename)
```

### Type Mapping (NDJSON → Excel)

| JSON Type | Excel Type | Notes |
|-----------|------------|-------|
| number | Number | Preserves int/float distinction |
| string | String | Text cells |
| boolean | Boolean | TRUE/FALSE |
| null | Blank | Empty cell |
| ISO date string | Date | Auto-detect and convert "2025-01-15" |
| Array/Object | String | JSON.stringify() |

### Multi-Sheet Writing

**Option 1**: Include `sheet` key in records
```json
{"sheet": "Sales", "Product": "Widget", "Revenue": 1000}
{"sheet": "Sales", "Product": "Gadget", "Revenue": 500}
{"sheet": "Costs", "Item": "Rent", "Amount": 2000}
```

**Option 2**: Multiple puts with `--sheet` flag
```bash
jn cat sales.json | jn put report.xlsx --sheet Sales
jn cat costs.json | jn put report.xlsx --sheet Costs --append
```

### Edge Cases

**Inconsistent keys across records**:
- Collect all unique keys from all records
- Use union of keys as columns
- Missing values → null (blank cells)

**Key ordering**:
- Use first record's key order as column order
- Or add `--columns Name,Age,City` flag for explicit ordering

**Excel limits**:
- Max 1,048,576 rows per sheet
- Max 16,384 columns per sheet
- Error if exceeded

**Special characters in sheet names**:
- Excel forbids: `[ ] : * ? / \`
- Sanitize automatically or error

### Example Workflows

**API response → Excel**:
```bash
jn cat https://api.example.com/users | jn put users.xlsx --header
```

**Filter and export**:
```bash
jn cat large-dataset.csv | jq 'select(.revenue > 1000)' | jn put high-value.xlsx
```

**Multi-sheet report**:
```bash
# Add sheet column with jq
jn cat sales.csv | jq '. + {sheet: "Sales"}' > /tmp/sales.ndjson
jn cat costs.csv | jq '. + {sheet: "Costs"}' > /tmp/costs.ndjson
cat /tmp/sales.ndjson /tmp/costs.ndjson | jn put report.xlsx --multi-sheet
```

## Implementation Notes

### Parser Registration

Add to `src/jn/jcparsers/excel_s.py`:

**NOT using JC**: Excel parsing is too complex for JC's paradigm. Implement directly.

### File Structure

```
src/jn/adapters/
  excel.py          # Main adapter logic
  excel_reader.py   # Streaming reader using openpyxl/xlrd
  excel_writer.py   # Buffering writer using openpyxl
```

### Auto-Detection

In `src/jn/cli/cat.py`, extend `_detect_file_parser()`:

```python
parser_map = {
    ".csv": "csv_s",
    ".tsv": "tsv_s",
    ".psv": "psv_s",
    ".xlsx": "excel",    # New
    ".xls": "excel",     # New
}
```

### Testing Strategy

**Unit tests**:
- Type conversion (dates, formulas, errors)
- Header row parsing
- Sheet selection logic
- Range parsing

**Integration tests**:
- Small test workbooks (2-3 sheets, 10-20 rows)
- Both .xls and .xlsx formats
- Merged cells
- Formulas (with expected values)
- Edge cases (empty rows, hidden columns)

**Golden stream tests**:
- test-fixtures/excel/simple.xlsx → expected NDJSON
- test-fixtures/excel/multi-sheet.xlsx → expected NDJSON
- Compare JSON structures (not string diffs)

**Performance tests**:
- Large file (100K rows) should stream without memory issues
- Measure memory usage in read_only mode vs normal mode

### Error Handling

```python
try:
    wb = load_workbook(filename, read_only=True)
except InvalidFileException:
    raise JnError("excel", filename, "Invalid Excel file format")
except PermissionError:
    raise JnError("excel", filename, "Permission denied")
```

**Specific errors**:
- File not found
- Corrupt workbook
- Sheet not found
- Invalid range syntax
- Excel file is password-protected

## Performance Characteristics

**Reading**:
- Streaming mode (.xlsx): ~50MB memory for any file size
- Legacy mode (.xls): Must load entire file (limited by xlrd)
- Speed: ~10K-50K rows/second depending on complexity

**Writing**:
- Must buffer all records in memory
- Writing speed: ~5K-20K rows/second
- Memory: ~100 bytes per cell on average

## Future Enhancements

**Phase 2 features** (not in initial implementation):
- Named ranges support: `--range TotalSales`
- Table detection: `--detect-tables` (requires lookahead)
- Cell styling preservation in passthrough mode
- Excel formulas in target adapter: `{"A1": "=SUM(B1:B10)"}`
- Pivot table extraction
- Chart metadata extraction

**Low priority**:
- .xlsb (binary workbook) support
- .xlsm (macro-enabled) support (security risk)
- Conditional formatting rules extraction

## Security Considerations

**Risks**:
- Macro viruses (.xlsm files)
- Formula injection (=cmd|'/c calc')
- XML bombs (billion laughs attack in .xlsx)
- Path traversal in sheet names

**Mitigations**:
- Refuse to open .xlsm files by default (add `--allow-macros` flag with warning)
- Use `data_only=True` to neutralize formulas
- Sanitize sheet names when writing
- Set reasonable file size limits (warn if >100MB)

## Dependencies

Add to `pyproject.toml`:
```toml
[tool.poetry.dependencies]
openpyxl = "^3.1.0"    # Modern .xlsx support
xlrd = "^2.0.0"        # Legacy .xls support
```

## Success Criteria

- [x] Can read both .xls and .xlsx files
- [x] Streams large files without loading into memory
- [x] Supports header row extraction
- [x] Handles multiple sheets
- [x] Converts dates to ISO 8601
- [x] Can write NDJSON → .xlsx with headers
- [x] Handles merged cells gracefully
- [x] Test coverage >85%
- [x] Works in cat/head/tail pipeline
- [x] Clear error messages for common failures
