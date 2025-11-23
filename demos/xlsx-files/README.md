# XLSX (Excel) Files Demo

This demo shows how to work with Microsoft Excel (.xlsx) files using JN.

## What You'll Learn

- Reading Excel spreadsheets into NDJSON
- Converting Excel to CSV/JSON/YAML
- Filtering and transforming Excel data
- Creating Excel files from other formats
- Working with multi-sheet workbooks

## Basic Operations

### Read Excel File

```bash
# Read Excel file as NDJSON
jn cat data.xlsx

# Read specific sheet
jn cat "data.xlsx?sheet=Sheet2"

# View first few rows
jn cat data.xlsx | jn head -n 5
```

### Convert Excel to Other Formats

```bash
# Excel → CSV
jn cat data.xlsx | jn put data.csv

# Excel → JSON
jn cat data.xlsx | jn put data.json

# Excel → YAML
jn cat data.xlsx | jn put data.yaml

# Excel → NDJSON
jn cat data.xlsx | jn put data.ndjson
```

### Create Excel from Other Formats

```bash
# CSV → Excel
jn cat data.csv | jn put output.xlsx

# JSON → Excel
jn cat data.json | jn put output.xlsx

# NDJSON → Excel
jn cat data.ndjson | jn put output.xlsx
```

## Working with Sample Data

This demo includes a sample Excel file (`budget.xlsx`) with financial data.

### View Budget Data

```bash
jn cat budget.xlsx
```

### Filter Data

```bash
# Find expenses over $500
jn cat budget.xlsx | \
  jn filter '(.amount | tonumber) > 500'

# Filter by category
jn cat budget.xlsx | \
  jn filter '.category == "Marketing"'

# Filter by date range (Q1)
jn cat budget.xlsx | \
  jn filter '.month | test("^(Jan|Feb|Mar)")'
```

### Transform Data

```bash
# Extract specific fields
jn cat budget.xlsx | \
  jn filter '{month: .month, expense: .description, cost: .amount}'

# Add calculated fields
jn cat budget.xlsx | \
  jn filter '. + {
    annual: ((.amount | tonumber) * 12),
    category_upper: (.category | ascii_upcase)
  }'
```

### Aggregate Data

```bash
# Total by category
jn cat budget.xlsx | \
  jq -s 'group_by(.category) | map({
    category: .[0].category,
    total: map(.amount | tonumber) | add,
    count: length
  }) | .[]'

# Monthly totals
jn cat budget.xlsx | \
  jq -s 'group_by(.month) | map({
    month: .[0].month,
    total: map(.amount | tonumber) | add
  }) | .[]'
```

## Multi-Sheet Workbooks

### List All Sheets

```bash
# Note: Currently reads default sheet
# Use openpyxl or pandas directly to list sheets
python3 << 'EOF'
from openpyxl import load_workbook
wb = load_workbook('workbook.xlsx')
for sheet in wb.sheetnames:
    print(sheet)
EOF
```

### Read Specific Sheet

```bash
jn cat "workbook.xlsx?sheet=Revenue"
jn cat "workbook.xlsx?sheet=Expenses"
```

### Process Multiple Sheets

```bash
# Process each sheet separately
jn cat "workbook.xlsx?sheet=Sheet1" | jn put sheet1.csv
jn cat "workbook.xlsx?sheet=Sheet2" | jn put sheet2.csv
```

## Pipeline Examples

### Excel → Filter → Save as CSV

```bash
jn cat budget.xlsx | \
  jn filter '.category == "Engineering"' | \
  jn put engineering_budget.csv
```

### Combine and Transform

```bash
# Read Excel, add calculations, save as JSON
jn cat budget.xlsx | \
  jn filter '. + {
    quarterly: ((.amount | tonumber) * 3),
    yearly: ((.amount | tonumber) * 12)
  }' | \
  jn put budget_projections.json
```

### Merge Multiple Excel Files

```bash
# Combine multiple Excel files
jn cat file1.xlsx > combined.ndjson
jn cat file2.xlsx >> combined.ndjson
jn cat file3.xlsx >> combined.ndjson

# Convert combined data to single Excel file
jn cat combined.ndjson | jn put merged.xlsx
```

## Creating Sample Data

The included script creates a sample budget Excel file:

```bash
./create_sample.py
```

This generates `budget.xlsx` with monthly budget data including:
- Month
- Category (Engineering, Marketing, Operations, etc.)
- Description
- Amount

## Run the Examples

Execute the provided script:

```bash
./run_examples.sh
```

This will:
- Create sample Excel file
- Demonstrate reading and filtering
- Show format conversions
- Create aggregated reports

## Implementation Details

### Dependencies

The XLSX plugin uses `openpyxl`:

```python
# /// script
# dependencies = ["openpyxl"]
# ///
```

UV automatically manages this dependency when you use JN.

### Reading

The XLSX plugin:
1. Opens the workbook with `openpyxl`
2. Reads the active sheet (or specified sheet)
3. Extracts header row (first row)
4. Streams remaining rows as NDJSON

### Writing

The XLSX plugin:
1. Collects NDJSON records from stdin
2. Extracts headers from first record's keys
3. Creates workbook with `openpyxl`
4. Writes header row and data rows
5. Saves as .xlsx file

## Limitations

- Currently reads/writes single sheet per operation
- Header must be in first row
- All data treated as text (no formula preservation)
- No styling/formatting preservation
- Large files (~100MB+) may use significant memory

## Best Practices

### For Large Files

```bash
# Use head/tail to limit data
jn cat large.xlsx | jn head -n 1000 | jn put sample.csv

# Filter early to reduce data
jn cat large.xlsx | \
  jn filter '.important == "yes"' | \
  jn put filtered.xlsx
```

### For Clean Data

```bash
# Remove empty rows
jn cat data.xlsx | \
  jn filter '. | to_entries | any(.value != "")'

# Handle missing values
jn cat data.xlsx | \
  jn filter 'with_entries(.value = (.value // "N/A"))'
```

## Error Handling

Errors are returned as NDJSON error records:

```json
{
  "_error": true,
  "type": "xlsx_error",
  "message": "File not found: data.xlsx"
}
```

## Next Steps

- See the CSV demo for more filtering techniques
- Check the HTTP demo for fetching remote Excel files
- Explore combining Excel data with APIs
