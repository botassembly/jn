# XLSX Format Plugin

## Overview
Implement a format plugin to read Excel (.xlsx) files and convert them to NDJSON. This enables processing spreadsheet data through JN pipelines.

## Goals
- Read XLSX files and convert to NDJSON (one object per row)
- Support multiple sheets (default to first sheet)
- Preserve data types (numbers, dates, text, booleans)
- Handle merged cells gracefully
- Support sheet selection by name or index
- Stream data row-by-row (don't load entire file in memory)

## Resources
**Test XLSX Files (Public URLs):**
- Wall Street Prep model: `https://s3.amazonaws.com/wsp_sample_file/excel-templates/financial-statement-model-sample.xlsx`
- UK ONS Internet Users: `https://www.ons.gov.uk/file?uri=/businessindustryandtrade/itandinternetindustry/datasets/internetusers/current/internetusers2020.xlsx`
- GitHub HuBMAP template: `https://raw.githubusercontent.com/hubmapconsortium/dataset-metadata-spreadsheet/main/sample-section/latest/sample-section.xlsx`
- Simple test file: `https://raw.githubusercontent.com/Russel88/COEF/master/ExampleData/test.xlsx`

## Dependencies
**Primary:** `openpyxl` (pure Python, no C dependencies, widely used)
- Most popular Python library for .xlsx files
- Read-only mode for memory efficiency
- Supports streaming large files

**Alternative:** `xlrd` (older, but simpler)
- Consider if openpyxl is too heavy

Add to PEP 723 dependencies:
```toml
dependencies = ["openpyxl>=3.0.0"]
```

## Technical Approach
- Implement `reads()` function only (write support later)
- Pattern matching: `.*\\.xlsx$` and `.*\\.xlsm$`
- Open workbook in read-only mode
- Default to first sheet unless `--sheet` specified
- First row = column headers (unless `--no-header`)
- Yield each row as dict with column names as keys
- Handle empty cells (null/None)
- Convert Excel dates to ISO 8601 strings

## Usage Examples
```bash
# Read XLSX file
jn cat data.xlsx | jn put output.json

# Fetch XLSX from URL and convert
jn cat https://example.com/data.xlsx | jn put output.csv

# Select specific sheet
jn cat data.xlsx --sheet "Sheet2" | jn filter '.revenue > 1000'

# Pipeline with HTTP + XLSX
jn cat https://s3.amazonaws.com/wsp_sample_file/excel-templates/financial-statement-model-sample.xlsx | jn head -n 10
```

## Out of Scope
- Writing XLSX files (writes() function) - add later if needed
- Formulas evaluation - just read cell values
- Formatting/styling information - data only
- Charts and images - ignore
- Password-protected files - error with clear message
- Very large files (>100MB) - streaming optimization later
- Multiple sheet output - one sheet at a time
- Macros (.xlsm) - read data only, ignore macros
- Excel binary format (.xls) - only .xlsx supported

## Success Criteria
- Can read small XLSX files (<10MB)
- Properly converts data types (numbers, dates, text)
- Handles missing values
- Works with HTTP plugin to fetch remote XLSX files
- Memory efficient (streaming row-by-row)
- Clear error messages for corrupted files
