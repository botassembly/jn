# Excel Source Adapter

## Overview

Excel adapter for reading .xlsx files and converting to NDJSON. Designed for streaming row-based data extraction from spreadsheets.

## Supported Format

- **.xlsx** - Modern XML-based Excel format (Excel 2007+)

**Note**: Legacy .xls format (Excel 97-2003) is not supported initially. Can be added later if users request it.

## Design Philosophy

Excel adapter treats spreadsheets as **data tables**, not hierarchical documents. Focus is on extracting rectangular data efficiently with streaming when possible.

## Library

- **openpyxl**: Mature Python library, supports read_only mode for streaming, handles formulas and merged cells

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

# Sheet selection
jn cat data.xlsx --sheet "Sales"    # Specific sheet by name
jn cat data.xlsx --sheet 2          # Sheet by index (1-based)
jn cat data.xlsx --all-sheets       # All sheets with sheet column

# Range selection
jn cat data.xlsx --range A1:D100    # Excel range notation
jn cat data.xlsx --skip-rows 5      # Skip first N rows
jn cat data.xlsx --max-rows 100     # Limit to N rows

# Row filtering
jn cat data.xlsx --no-empty-rows    # Skip rows where all cells are empty
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
- data_only=True gives calculated values (not formula text)

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
| Formula | number/string | Calculated value only |
| Blank | null | Empty cell → null |
| Error | string | "#DIV/0!", "#N/A", etc. |

### Edge Cases

**Merged cells**:
- In streaming mode: Only first cell has value, rest are null
- This is acceptable for data extraction (merged cells are rare in data tables)

**Multiple header rows**:
- `--header` uses first row only
- For complex headers, use `--skip-rows` to skip manually

**Hidden rows/columns**:
- Included by default (read_only mode doesn't track hidden state)

**Protected sheets**:
- Read-only works fine

**Large numbers**:
- Excel stores numbers as float64
- May lose precision for very large integers (>15 digits)

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

**Process all sheets separately**:
```bash
# Get list of sheet names
jn cat workbook.xlsx --all-sheets | jq -r '.sheet' | sort -u

# Process each sheet
jn cat workbook.xlsx --sheet "Sales" | jq '...' > sales.json
jn cat workbook.xlsx --sheet "Costs" | jq '...' > costs.json
```

## Implementation Notes

### Parser Registration

**NOT using JC**: Excel parsing is too complex for JC's paradigm. Implement directly as native adapter.

### File Structure

```
src/jn/adapters/
  excel.py          # Main adapter logic
  excel_reader.py   # Streaming reader using openpyxl
```

### Auto-Detection

In `src/jn/cli/cat.py`, extend `_detect_file_parser()`:

```python
parser_map = {
    ".csv": "csv_s",
    ".tsv": "tsv_s",
    ".psv": "psv_s",
    ".xlsx": "excel",    # New
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
- Merged cells
- Formulas (with expected calculated values)
- Edge cases (empty rows, all sheets)

**Golden stream tests**:
- test-fixtures/excel/simple.xlsx → expected NDJSON
- test-fixtures/excel/multi-sheet.xlsx → expected NDJSON
- Compare JSON structures (not string diffs)

**Performance tests**:
- Large file (100K rows) should stream without memory issues
- Measure memory usage in read_only mode

### Error Handling

```python
try:
    wb = load_workbook(filename, read_only=True, data_only=True)
except InvalidFileException:
    raise JnError("excel", filename, "Invalid Excel file format")
except PermissionError:
    raise JnError("excel", filename, "Permission denied")
```

**Specific errors**:
- File not found
- Corrupt workbook
- Sheet not found (when using --sheet)
- Invalid range syntax
- Password-protected files

## Performance Characteristics

**Reading**:
- Streaming mode: ~50MB memory for any file size
- Speed: ~10K-50K rows/second depending on complexity

## Future Enhancements

**Phase 2 features** (not in initial implementation):
- .xls (legacy format) support if users request it
- Named ranges support: `--range TotalSales`
- Table detection: `--detect-tables` (requires lookahead)
- Cell styling information extraction
- Formula text extraction with `--show-formulas` flag
- Writing Excel files (target adapter)

## Security Considerations

**Risks**:
- Macro viruses (.xlsm files)
- Formula injection (=cmd|'/c calc')
- XML bombs (billion laughs attack in .xlsx)
- Path traversal in sheet names

**Mitigations**:
- Refuse to open .xlsm (macro-enabled) files by default
- Use `data_only=True` to neutralize formulas (get values only)
- Set reasonable file size limits (warn if >100MB)

## Dependencies

Add to `pyproject.toml`:
```toml
[tool.poetry.dependencies]
openpyxl = "^3.1.0"    # .xlsx support
```

## Success Criteria

- [x] Can read .xlsx files
- [x] Streams large files without loading into memory
- [x] Supports header row extraction
- [x] Handles multiple sheets (--sheet, --all-sheets)
- [x] Converts dates to ISO 8601
- [x] Handles merged cells gracefully (first cell has value)
- [x] Test coverage >85%
- [x] Works in cat/head/tail pipeline
- [x] Clear error messages for common failures
