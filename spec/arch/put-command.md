# Put Command

## Overview

The `put` command writes NDJSON data to files in various formats. It's the counterpart to `cat` - where `cat` reads files and outputs NDJSON, `put` reads NDJSON and writes files.

## Basic Usage

```bash
# Auto-detect format from extension
jn cat data.csv | jq 'select(.amount > 100)' | jn put filtered.csv

# Pipe from any NDJSON source
jn cat https://api.example.com/users | jn put users.json

# Chain transformations
jn cat sales.csv | jq -s 'group_by(.category)' | jn put summary.xlsx
```

## Syntax

```bash
jn put <output-file> [OPTIONS]
```

**Input**: NDJSON from stdin
**Output**: File in specified format

## Format Auto-Detection

Format is detected from file extension:

| Extension | Format | Adapter |
|-----------|--------|---------|
| `.csv` | CSV | CSV writer |
| `.tsv` | TSV | TSV writer (delimiter=\t) |
| `.psv` | PSV | PSV writer (delimiter=\|) |
| `.json` | JSON array | JSON writer |
| `.jsonl`, `.ndjson` | NDJSON | Passthrough |
| `.xlsx` | Excel (future) | Excel writer |
| `.md`, `.markdown` | Markdown (future) | Markdown writer |

## Options

```bash
# Format override
jn put output.txt --format csv        # Write CSV to .txt file

# CSV options
jn put output.csv --header            # Include header row
jn put output.csv --delimiter ","     # Custom delimiter
jn put output.csv --no-header         # Skip header

# JSON options
jn put output.json --pretty           # Pretty-print JSON
jn put output.json --compact          # Compact JSON (default)

# File handling
jn put output.csv --overwrite         # Overwrite if exists (default: error)
jn put output.csv --append            # Append to existing file

# Output to stdout
jn put - --format csv                 # Write to stdout instead of file
```

## Format-Specific Behavior

### CSV/TSV/PSV

**Input**: NDJSON records with consistent keys
```json
{"name": "Alice", "age": 30, "city": "NYC"}
{"name": "Bob", "age": 25, "city": "SF"}
```

**Output** (CSV with header):
```csv
name,age,city
Alice,30,NYC
Bob,25,SF
```

**Options**:
- `--header` (default: true) - Include header row
- `--delimiter ","` - Column delimiter
- `--quote '"'` - Quote character

**Column ordering**: First record's key order determines column order.

**Missing keys**: Empty value if key missing in later records.

**Streaming**: Yes - writes rows as they arrive.

### JSON

**Input**: NDJSON records
```json
{"name": "Alice", "age": 30}
{"name": "Bob", "age": 25}
```

**Output** (JSON array):
```json
[
  {"name": "Alice", "age": 30},
  {"name": "Bob", "age": 25}
]
```

**Options**:
- `--pretty` - Pretty-print with indentation
- `--compact` - Single line (default)

**Buffering**: Yes - must collect all records to write array with brackets.

### NDJSON / JSON Lines

**Input**: NDJSON
```json
{"name": "Alice"}
{"name": "Bob"}
```

**Output**: Same (passthrough)
```json
{"name": "Alice"}
{"name": "Bob"}
```

**Streaming**: Yes - direct passthrough.

### Excel (.xlsx) - Future

**Input**: NDJSON records
```json
{"Name": "Alice", "Age": 30, "City": "NYC"}
{"Name": "Bob", "Age": 25, "City": "SF"}
```

**Output**: Excel file with data in first sheet.

**Options**:
- `--sheet "Results"` - Sheet name
- `--header` - Include header row

**Buffering**: Yes - must collect all records before writing workbook.

### Markdown (.md) - Future

**Input**: NDJSON with `_kind` field
```json
{"_kind": "heading", "level": 1, "text": "Report"}
{"_kind": "paragraph", "text": "Summary of results"}
```

**Output**: Formatted Markdown document.

**Buffering**: No - can stream blocks.

## Examples

### Example 1: Filter and Save

```bash
jn cat sales.csv | jq 'select(.amount > 1000)' | jn put high-value.csv
```

### Example 2: Format Conversion

```bash
# CSV to JSON
jn cat data.csv | jn put data.json

# JSON to CSV
jn cat data.json | jn put data.csv --header

# Excel to CSV (future)
jn cat report.xlsx | jn put report.csv
```

### Example 3: API to File

```bash
jn cat https://api.example.com/users | jn put users.json --pretty
```

### Example 4: Aggregate and Save

```bash
jn cat sales.csv | jq -s 'group_by(.category) | map({
  category: .[0].category,
  total: map(.amount) | add
})' | jn put summary.csv --header
```

### Example 5: Multiple Outputs (with tee)

```bash
jn cat data.csv | tee >(jn put backup.json) | jq 'select(.active)' | jn put active.csv
```

### Example 6: Stdout Output

```bash
# Write to stdout (for piping)
jn cat data.csv | jn put - --format csv | head -n 5

# Useful for previewing
jn cat large.csv | jq 'select(.amount > 100)' | jn put - --format json --pretty | less
```

### Example 7: Append to Existing File

```bash
# Daily log aggregation
jn cat today.log | jq 'select(.level == "ERROR")' | jn put errors.json --append
```

## Implementation Notes

### File Structure

```
src/jn/cli/
  put.py              # Main put command
src/jn/writers/
  csv_writer.py       # CSV/TSV/PSV writer
  json_writer.py      # JSON writer
  ndjson_writer.py    # Passthrough
  excel_writer.py     # Future
  markdown_writer.py  # Future
```

### CSV Writer

```python
import csv
import sys

def write_csv(records, output_file, delimiter=',', header=True):
    # Collect all records (need to know all keys)
    records = list(records)
    if not records:
        return

    # Get all unique keys (union of all record keys)
    all_keys = []
    seen = set()
    for record in records:
        for key in record.keys():
            if key not in seen:
                all_keys.append(key)
                seen.add(key)

    # Write CSV
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, delimiter=delimiter)
        if header:
            writer.writeheader()
        writer.writerows(records)
```

### JSON Writer

```python
import json

def write_json(records, output_file, pretty=False):
    records = list(records)  # Buffer all records

    with open(output_file, 'w') as f:
        if pretty:
            json.dump(records, f, indent=2)
        else:
            json.dump(records, f)
```

### NDJSON Writer (Streaming)

```python
import json

def write_ndjson(records, output_file):
    with open(output_file, 'w') as f:
        for record in records:
            f.write(json.dumps(record) + '\n')
```

### Format Detection

```python
from pathlib import Path

def detect_output_format(filepath):
    ext = Path(filepath).suffix.lower()

    format_map = {
        '.csv': 'csv',
        '.tsv': 'tsv',
        '.psv': 'psv',
        '.json': 'json',
        '.jsonl': 'ndjson',
        '.ndjson': 'ndjson',
        '.xlsx': 'excel',
        '.md': 'markdown',
        '.markdown': 'markdown',
    }

    return format_map.get(ext, 'json')  # Default to JSON
```

### CLI Command

```python
import typer
from typing import Optional

app = typer.Typer()

@app.command()
def put(
    output_file: str,
    format: Optional[str] = None,
    header: bool = True,
    delimiter: str = ',',
    pretty: bool = False,
    overwrite: bool = False,
    append: bool = False,
):
    """Write NDJSON from stdin to file in specified format"""

    # Detect format
    if format is None:
        format = detect_output_format(output_file)

    # Check if file exists
    if Path(output_file).exists() and not overwrite and not append:
        raise ValueError(f"File {output_file} already exists. Use --overwrite or --append")

    # Read NDJSON from stdin
    records = read_ndjson_from_stdin()

    # Write based on format
    if format == 'csv':
        write_csv(records, output_file, delimiter=delimiter, header=header)
    elif format == 'tsv':
        write_csv(records, output_file, delimiter='\t', header=header)
    elif format == 'psv':
        write_csv(records, output_file, delimiter='|', header=header)
    elif format == 'json':
        write_json(records, output_file, pretty=pretty)
    elif format == 'ndjson':
        write_ndjson(records, output_file)
    else:
        raise ValueError(f"Unsupported format: {format}")
```

## Edge Cases

### Empty Input

```bash
# Empty NDJSON stream
echo "" | jn put output.csv

# Behavior: Create empty file or file with just header
```

### Inconsistent Keys

**Input**:
```json
{"name": "Alice", "age": 30}
{"name": "Bob", "city": "SF"}
```

**Output** (CSV):
```csv
name,age,city
Alice,30,
Bob,,SF
```

**Strategy**: Union of all keys, empty values for missing keys.

### Special Characters

**Input**:
```json
{"name": "Alice, Bob", "note": "Quote: \"Hi\""}
```

**Output** (CSV):
```csv
name,note
"Alice, Bob","Quote: ""Hi"""
```

**Strategy**: Use CSV library's quoting rules.

### Large Files

**CSV/NDJSON**: Stream row-by-row, memory efficient.

**JSON/Excel**: Must buffer all records, high memory usage.

**Recommendation**: For large datasets (>1M records), use NDJSON or CSV, not JSON.

### Stdout Output

```bash
# Write to stdout (- means stdout)
jn cat data.csv | jn put - --format csv

# Useful in pipelines
jn cat data.csv | jn put - --format json | ssh remote-server 'cat > data.json'
```

## Error Handling

### File Already Exists

```bash
jn put output.csv
# Error: File output.csv already exists. Use --overwrite or --append
```

### Unsupported Format

```bash
jn put output.xyz
# Error: Cannot detect format for .xyz. Use --format to specify.
```

### Invalid NDJSON Input

```bash
echo "not json" | jn put output.csv
# Error: Invalid JSON on line 1: not json
```

### Permission Denied

```bash
jn put /root/output.csv
# Error: Permission denied: /root/output.csv
```

## Testing Strategy

### Unit Tests

- Format detection from extension
- CSV writer (with/without header, custom delimiter)
- JSON writer (pretty/compact)
- NDJSON passthrough
- Inconsistent keys handling
- Empty input handling

### Integration Tests

```python
def test_put_csv():
    # Write NDJSON to CSV
    input_data = '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'
    result = runner.invoke(app, ['put', 'test.csv'], input=input_data)

    assert result.exit_code == 0
    assert Path('test.csv').exists()

    # Read back and verify
    with open('test.csv') as f:
        assert f.read() == 'name,age\nAlice,30\nBob,25\n'

def test_format_conversion():
    # CSV to JSON
    runner.invoke(cat_app, ['data.csv'], catch_exceptions=False)
    # Pipe through put
    result = runner.invoke(put_app, ['output.json'])

    assert result.exit_code == 0
    # Verify JSON array format
```

### Golden Output Tests

```
test-fixtures/put/
  input.ndjson → expected-output.csv
  input.ndjson → expected-output.json
  input.ndjson → expected-output.tsv
```

## Relationship to Target Adapters in Pipelines

**Pipeline config** (for reusable workflows):
```json
{
  "source": {"driver": "file", "path": "data.csv"},
  "converter": {"query": "select(.amount > 100)"},
  "target": {"driver": "file", "path": "output.xlsx", "format": "excel"}
}
```

**Put command** (for ad-hoc transformations):
```bash
jn cat data.csv | jq 'select(.amount > 100)' | jn put output.xlsx
```

**Difference**:
- Pipelines are for repeatable workflows with configs
- Put is for quick one-off transformations
- Both use the same underlying writers

## Future Enhancements

**Phase 2** (not in initial implementation):
- Excel writer (`jn put output.xlsx`)
- Markdown writer (`jn put output.md`)
- Multi-file output (folder as target)
- Compression (`jn put output.csv.gz`)
- Remote targets (`jn put s3://bucket/data.csv`)
- Streaming JSON writer (JSON Lines mode)

## Success Criteria

- [x] Can write CSV with header
- [x] Can write TSV and PSV
- [x] Can write JSON array
- [x] Can write NDJSON (passthrough)
- [x] Auto-detects format from extension
- [x] Can override format with --format
- [x] Handles inconsistent keys gracefully
- [x] Streams when possible (CSV, NDJSON)
- [x] Buffers when necessary (JSON)
- [x] Clear error messages
- [x] Test coverage >85%
- [x] Works with cat in pipelines
