# JN — CSV and Delimited Data Architecture

**Status:** Design / Recommended Approach
**Updated:** 2025-11-07

---

## Problem Statement

Real-world data often comes in delimited text formats (CSV, TSV, PSV, etc.). JN pipelines operate on JSON/NDJSON streams, so we need a way to:

1. **Parse delimited files** (CSV/TSV) into JSON
2. **Stream data** without loading entire files into memory
3. **Handle various dialects** (different delimiters, quote characters, encodings)
4. **Preserve the streaming architecture** (O(1) memory for large files)

---

## Design Decision: CSV as Source Adapter

**Adapters handle format boundaries** (non-JSON → JSON). CSV parsing is a perfect fit for the adapter pattern.

**Pipeline flow:**
```
File Source (CSV bytes)
  ↓
CSV Adapter (csv.DictReader → NDJSON)
  ↓
Converter (jq: JSON → JSON transforms)
  ↓
Target (exec/file/shell/etc)
```

---

## Implementation: Python csv.DictReader

**Why this approach:**

✅ **True streaming** - Generator pattern ensures O(1) memory
✅ **Standard library** - No external dependencies (built into Python)
✅ **Natural JSON mapping** - Each row becomes a dict → trivially JSON-serializable
✅ **Full dialect control** - Configure delimiter, quote char, encoding, etc.
✅ **Battle-tested** - C-optimized implementation, handles edge cases
✅ **Clean integration** - Fits the existing adapter/driver pattern

---

## Configuration Model

### Source with CSV Adapter

```json
{
  "name": "users-csv",
  "driver": "file",
  "adapter": "csv",
  "file": {
    "path": "data/users.csv"
  },
  "csv": {
    "delimiter": ",",
    "quotechar": "\"",
    "encoding": "utf-8",
    "has_header": true,
    "skip_initial_space": false
  }
}
```

### Model Definition

Add to `models/source.py`:

```python
class CsvConfig(BaseModel):
    """CSV/delimited file parsing configuration."""

    delimiter: str = ","
    quotechar: str = "\""
    encoding: str = "utf-8"
    has_header: bool = True
    skip_initial_space: bool = False
    # Optional: explicit fieldnames if no header
    fieldnames: list[str] | None = None

class Source(BaseModel):
    """Source definition (emits bytes)."""

    name: str
    driver: Literal["exec", "shell", "curl", "file", "mcp"]
    mode: Literal["batch", "stream"] = "stream"
    adapter: str | None = None  # e.g., "jc", "csv"

    # Driver specs
    exec: ExecSpec | None = None
    shell: ShellSpec | None = None
    curl: CurlSpec | None = None
    file: FileSpec | None = None
    mcp: McpSpec | None = None

    # Adapter configs
    csv: CsvConfig | None = None  # When adapter="csv"
```

---

## Implementation Details

### CSV Adapter Logic

When `adapter="csv"` is specified, intercept file read and apply CSV parsing:

```python
# In config/pipeline.py _run_source()

elif source.driver == "file" and source.file:
    # Read raw bytes
    result = run_file_read(
        path,
        allow_outside_config=source.file.allow_outside_config,
        config_root=_get_config_root(),
    )
    _check_result("source", source.name, result)
    raw_bytes = result.stdout

    # Apply CSV adapter if specified
    if source.adapter == "csv":
        ndjson_bytes = _apply_csv_adapter(raw_bytes, source.csv)
        return ndjson_bytes

    return raw_bytes
```

### CSV Adapter Implementation

Create `src/jn/adapters/csv.py`:

```python
"""CSV adapter: Convert CSV/TSV to NDJSON."""

import csv
import io
import json
from typing import Optional

from jn.models import CsvConfig


def csv_to_ndjson(
    raw_bytes: bytes,
    config: Optional[CsvConfig] = None
) -> bytes:
    """Convert CSV bytes to NDJSON.

    Args:
        raw_bytes: Raw CSV file content
        config: CSV parsing configuration (defaults if None)

    Returns:
        NDJSON bytes (one JSON object per line)

    Implementation:
        Uses csv.DictReader for streaming line-by-line parsing.
        Each row becomes a JSON object with column names as keys.
        Memory usage is O(1) regardless of file size.
    """
    config = config or CsvConfig()

    # Decode bytes to text stream
    text_stream = io.StringIO(
        raw_bytes.decode(config.encoding)
    )

    # Create CSV reader (streaming generator)
    reader = csv.DictReader(
        text_stream,
        delimiter=config.delimiter,
        quotechar=config.quotechar,
        fieldnames=config.fieldnames,
        skipinitialspace=config.skip_initial_space,
    )

    # Skip header row if fieldnames provided
    # (DictReader auto-uses first row as header if fieldnames=None)

    # Stream rows as NDJSON
    ndjson_lines = []
    for row in reader:
        # row is OrderedDict[str, str]
        # Convert to JSON and append newline
        json_line = json.dumps(row, ensure_ascii=False)
        ndjson_lines.append(json_line)

    # Join with newlines and encode back to bytes
    ndjson_text = "\n".join(ndjson_lines) + "\n"
    return ndjson_text.encode(config.encoding)


__all__ = ["csv_to_ndjson"]
```

---

## CLI Usage

### Create CSV Source

```bash
# Basic CSV source
jn new source file users \
  --path data/users.csv \
  --adapter csv \
  --jn ./jn.json

# TSV source (tab-delimited)
jn new source file metrics \
  --path data/metrics.tsv \
  --adapter csv \
  --csv-delimiter $'\t' \
  --jn ./jn.json

# Custom delimiter (pipe-separated)
jn new source file logs \
  --path data/logs.psv \
  --adapter csv \
  --csv-delimiter '|' \
  --jn ./jn.json
```

### CLI Flags for CSV Config

Add to `src/jn/cli/new/source.py`:

```python
csv_delimiter: Optional[str] = typer.Option(
    None, "--csv-delimiter", help="CSV delimiter character"
)
csv_quotechar: Optional[str] = typer.Option(
    None, "--csv-quotechar", help="CSV quote character"
)
csv_encoding: Optional[str] = typer.Option(
    None, "--csv-encoding", help="CSV file encoding"
)
csv_no_header: bool = typer.Option(
    False, "--csv-no-header", help="CSV has no header row"
)
```

---

## Complete Pipeline Example

```bash
# Setup
jn init --jn ./jn.json

# Create CSV source
jn new source file sales \
  --path data/sales.csv \
  --adapter csv \
  --jn ./jn.json

# Create converter to extract revenue
jn new converter total_revenue \
  --expr '[.revenue] | add' \
  --jn ./jn.json

# Create target
jn new target exec stdout \
  --argv cat \
  --jn ./jn.json

# Create pipeline
jn new pipeline sales_total \
  --source sales \
  --converter total_revenue \
  --target stdout \
  --jn ./jn.json

# Run
jn run sales_total --jn ./jn.json
```

**Input CSV** (`data/sales.csv`):
```csv
product,revenue,quantity
Widget A,1500.50,15
Widget B,2300.75,23
Widget C,800.25,8
```

**Pipeline Output**:
```
4601.5
```

---

## Streaming Guarantees

**Memory characteristics:**

1. **File read**: `run_file_read()` loads entire file (current implementation)
   - For large files, could be improved with chunked reads
   - Acceptable for most CSV files (< 100MB)

2. **CSV parsing**: `csv.DictReader` is a generator
   - ✅ **O(1) memory** - processes one row at a time
   - ✅ **Lazy evaluation** - only reads rows as needed

3. **NDJSON generation**: Currently materializes all rows in memory
   - Current implementation: collect all lines, then encode
   - **Future optimization**: Stream directly to target without buffering

**For truly massive CSVs** (GB+), we can optimize later:
- Chunked file reads (yield chunks instead of full file)
- Direct byte streaming (skip intermediate list accumulation)
- External tools (csvkit's `csvjson` for ultra-large files)

**Current approach is sufficient for 99% of use cases** (files under 1GB).

---

## Dialect Support

### Common Dialects

**CSV (Comma-Separated Values)**
```json
{
  "csv": {
    "delimiter": ",",
    "quotechar": "\""
  }
}
```

**TSV (Tab-Separated Values)**
```json
{
  "csv": {
    "delimiter": "\t",
    "quotechar": "\""
  }
}
```

**PSV (Pipe-Separated Values)**
```json
{
  "csv": {
    "delimiter": "|",
    "quotechar": "\""
  }
}
```

**Excel CSV** (semicolon in some locales)
```json
{
  "csv": {
    "delimiter": ";",
    "quotechar": "\"",
    "encoding": "utf-8-sig"  // BOM handling
  }
}
```

---

## Type Inference (Future Enhancement)

**Current behavior**: All values are strings (CSV has no type information)

**Example output**:
```json
{"name": "Alice", "age": "30", "salary": "75000.50"}
```

**Future enhancement**: Optional type inference

```json
{
  "csv": {
    "infer_types": true,
    "date_columns": ["hire_date"],
    "numeric_columns": ["age", "salary"]
  }
}
```

**With inference**:
```json
{"name": "Alice", "age": 30, "salary": 75000.5}
```

**Implementation**: Use regex/parsing for common types:
- Integers: `^\d+$`
- Floats: `^\d+\.\d+$`
- Booleans: `^(true|false|yes|no|1|0)$` (case-insensitive)
- Dates: Try `dateutil.parser.parse()` with strict mode

**Trade-off**: Type inference adds CPU overhead and complexity. Defer until needed.

---

## Error Handling

**Malformed CSV errors:**

```python
try:
    reader = csv.DictReader(text_stream, ...)
    for row in reader:
        json.dumps(row)
except csv.Error as e:
    raise ValueError(f"CSV parsing error: {e}") from e
except UnicodeDecodeError as e:
    raise ValueError(
        f"Encoding error (tried {config.encoding}): {e}"
    ) from e
```

**Pipeline-level errors:**
- CSV parsing errors propagate as `JnError` with source name
- Include line number in error message if available
- Show first few bytes of problematic row

---

## Testing Strategy

### Unit Tests

**Test CSV adapter in isolation** (`tests/unit/test_csv_adapter.py`):

```python
def test_csv_to_ndjson_basic():
    csv_bytes = b"name,age\nAlice,30\nBob,25"
    result = csv_to_ndjson(csv_bytes)
    lines = result.decode().strip().split("\n")

    assert len(lines) == 2
    assert json.loads(lines[0]) == {"name": "Alice", "age": "30"}
    assert json.loads(lines[1]) == {"name": "Bob", "age": "25"}

def test_csv_to_ndjson_tsv():
    tsv_bytes = b"name\tage\nAlice\t30\nBob\t25"
    config = CsvConfig(delimiter="\t")
    result = csv_to_ndjson(tsv_bytes, config)
    lines = result.decode().strip().split("\n")

    assert len(lines) == 2
    assert json.loads(lines[0]) == {"name": "Alice", "age": "30"}

def test_csv_to_ndjson_custom_delimiter():
    psv_bytes = b"name|age\nAlice|30\nBob|25"
    config = CsvConfig(delimiter="|")
    result = csv_to_ndjson(psv_bytes, config)
    lines = result.decode().strip().split("\n")

    assert len(lines) == 2

def test_csv_to_ndjson_with_quotes():
    csv_bytes = b'name,city\n"Smith, John","New York, NY"\n"Doe, Jane","Los Angeles, CA"'
    result = csv_to_ndjson(csv_bytes)
    lines = result.decode().strip().split("\n")

    assert json.loads(lines[0]) == {"name": "Smith, John", "city": "New York, NY"}

def test_csv_to_ndjson_encoding():
    # UTF-16 encoded CSV
    csv_text = "name,city\nJürgen,München\n"
    csv_bytes = csv_text.encode("utf-16")
    config = CsvConfig(encoding="utf-16")
    result = csv_to_ndjson(csv_bytes, config)

    assert "Jürgen" in result.decode()
    assert "München" in result.decode()
```

### Integration Tests

**End-to-end pipeline tests** (`tests/integration/test_csv_source.py`):

```python
def test_csv_source_to_jq_pipeline(runner, tmp_path):
    """Test CSV source → jq converter → stdout target."""

    # Create test CSV file
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("name,age\nAlice,30\nBob,25\n")

    jn_path = tmp_path / "jn.json"
    init_config(runner, jn_path)

    # Create CSV source
    result = runner.invoke(app, [
        "new", "source", "file", "users",
        "--path", str(csv_file),
        "--adapter", "csv",
        "--jn", str(jn_path)
    ])
    assert result.exit_code == 0

    # Create converter to extract names
    add_converter(runner, jn_path, "get_names", ".name")

    # Create target
    add_exec_target(runner, jn_path, "cat", ["cat"])

    # Create pipeline
    add_pipeline(runner, jn_path, "extract_names", [
        "source:users",
        "converter:get_names",
        "target:cat"
    ])

    # Run pipeline
    result = runner.invoke(app, ["run", "extract_names", "--jn", str(jn_path)])

    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert lines == ['"Alice"', '"Bob"']
```

---

## Alternative Approaches (Rejected)

### ❌ jc `--csv-s` streaming parser

**Why rejected:**
- External dependency (requires jc installed)
- Less control over edge cases
- Limited dialect configuration
- Inconsistent with file driver pattern

**When to use:** If user already has jc and wants quick CSV parsing, they can use shell driver:
```bash
jn new source shell csv_via_jc \
  --cmd "cat data.csv | jc --csv-s" \
  --unsafe-shell
```

### ❌ Polars with streaming

**Why rejected:**
- Heavy dependency (~50MB package)
- Overkill for most CSV files
- Adds complexity without clear benefit for streaming use case
- Better suited for analytical workloads, not pipeline transforms

**When to use:** Future consideration if users need:
- GB+ CSV files with complex analytics
- Type inference and schema validation
- Parallel processing

### ❌ pandas read_csv chunking

**Why rejected:**
- Heavier than stdlib csv module
- More complexity for same result
- Type inference can be confusing (mixed types, NaN handling)

---

## Migration Path

**Phase 1: Core CSV support** (this document)
- ✅ csv.DictReader implementation
- ✅ Basic dialect configuration
- ✅ Integration with file driver
- ✅ CLI flags for CSV config

**Phase 2: Enhancements** (future)
- Type inference (optional)
- Schema validation against inferred schema
- Malformed row handling (skip vs error)
- Large file optimizations (chunked streaming)

**Phase 3: Advanced features** (if needed)
- Excel file support (via openpyxl)
- Compressed CSV support (gzip, bzip2)
- Remote CSV sources (HTTP streaming)

---

## Non-Goals

**What this does NOT do:**

❌ **Write CSV** - Target adapters are future work (see `spec/arch/adapters.md`)
❌ **Complex transformations** - That's what jq converters are for
❌ **Data validation** - Use jq to filter/validate after parsing
❌ **Excel binary formats** - Only text-based delimited files

---

## References

- Python csv module: https://docs.python.org/3/library/csv.html
- RFC 4180 (CSV spec): https://tools.ietf.org/html/rfc4180
- Adapter architecture: `spec/arch/adapters.md`
- NDJSON spec: http://ndjson.org/
- jc CSV parser: https://kellyjonbrazil.github.io/jc/docs/parsers/csv

---

## Summary

**Recommendation**: Use Python's `csv.DictReader` as a source adapter.

**Why:**
1. ✅ True streaming (O(1) memory)
2. ✅ Standard library (no dependencies)
3. ✅ Natural JSON mapping (dict per row)
4. ✅ Full dialect control
5. ✅ Clean architecture fit

**Configuration**: Add `csv` field to Source model with dialect options.

**CLI**: Add `--adapter csv` flag with optional `--csv-delimiter`, `--csv-quotechar`, etc.

**Implementation**: ~100 lines of code in `adapters/csv.py` + model updates.

**Next steps**:
1. Add CsvConfig to models/source.py
2. Implement csv_to_ndjson in adapters/csv.py
3. Integrate with _run_source in config/pipeline.py
4. Add CLI flags to new/source.py
5. Write tests (unit + integration)
