# Format Plugins - Design

## Overview

Format plugins convert between file formats and NDJSON. They power `jn cat` (reading) and `jn put` (writing), enabling universal data interchange.

## Why Format Plugins?

Data exists in many formats: CSV, JSON, YAML, TOML, Markdown, tables. JN uses NDJSON as the universal interchange format, and format plugins are the translators.

**Philosophy:** JN pipelines are NDJSON streams. Format plugins are the entry/exit points.

```
CSV → reads() → NDJSON → filter → filter → writes() → JSON
```

## Plugin Types

### 1. **Bidirectional Formats** (Read + Write)

Formats that can convert both ways:

| Plugin | Reads | Writes | Use Case |
|--------|-------|--------|----------|
| `csv_` | ✅ | ✅ | Spreadsheets, exports |
| `json_` | ✅ | ✅ | APIs, config files |
| `yaml_` | ✅ | ✅ | Config files |
| `toml_` | ✅ | ✅ | Config files |
| `markdown_` | ✅ | ✅ | Documentation |

**Pattern:**
```python
def reads(config) -> Iterator[dict]:
    """File → NDJSON"""

def writes(config) -> None:
    """NDJSON → File"""
```

### 2. **Display-Only Formats** (Write Only)

Formats for human viewing, not data interchange:

| Plugin | Reads | Writes | Use Case |
|--------|-------|--------|----------|
| `tabulate_` | ❌ | ✅ | Pretty tables for terminals |
| `html_` | ❌ | ✅ | HTML tables (future) |
| `ascii_art_` | ❌ | ✅ | ASCII visualizations (future) |

**Why write-only?** These formats are for presentation. You can't reliably parse an ASCII table back to data.

**Pattern:**
```python
def writes(config) -> None:
    """NDJSON → Pretty display"""
    # No reads() function
```

## Format Plugin Architecture

### Reading (File → NDJSON)

**Goal:** Convert file format to stream of JSON objects.

**Example: CSV**
```python
def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read CSV from stdin, yield NDJSON records."""
    reader = csv.DictReader(sys.stdin)
    yield from reader
```

**Input:**
```csv
name,age,city
Alice,30,NYC
Bob,25,SF
```

**Output:**
```json
{"name": "Alice", "age": 30, "city": "NYC"}
{"name": "Bob", "age": 25, "city": "SF"}
```

**Streaming:** One line at a time → constant memory.

### Writing (NDJSON → File)

**Goal:** Convert stream of JSON objects to file format.

**Example: CSV**
```python
def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, write CSV to stdout."""
    # Collect records to determine columns
    records = []
    for line in sys.stdin:
        records.append(json.loads(line))

    # Get all keys (union across records)
    all_keys = ...

    # Write CSV with header
    writer = csv.DictWriter(sys.stdout, fieldnames=all_keys)
    writer.writeheader()
    writer.writerows(records)
```

**Input:**
```json
{"name": "Alice", "age": 30}
{"name": "Bob", "age": 25, "city": "SF"}
```

**Output:**
```csv
name,age,city
Alice,30,
Bob,25,SF
```

**Note:** CSV requires knowing all columns upfront → must buffer records. This is a CSV limitation, not a JN limitation.

## Tabulate Plugin (Display Format)

### Purpose

Pretty-print NDJSON as human-readable tables.

**Use case:** Quick inspection, reports, terminal output.

**Not for:** Data interchange, parsing, pipelines to other tools.

### Why Write-Only?

Tables are **display formats**, like syntax-highlighted code or ASCII art. They're for humans, not machines.

**Can't parse back:**
```
+--------+-------+
| name   |   age |
+========+=======+
| Alice  |    30 |
+--------+-------+
```

How do you know where one cell ends and another begins? What if data contains `|` or `+`? Ambiguous.

**Contrast with CSV:**
```csv
name,age
Alice,30
```

Unambiguous - commas delimit, quotes escape.

### Implementation

```python
def writes(config: Optional[dict] = None) -> None:
    """NDJSON → Pretty table."""
    records = []
    for line in sys.stdin:
        records.append(json.loads(line))

    table = tabulate(records, headers="keys", tablefmt="grid")
    print(table)
```

**No `reads()` function** - tables are output-only.

### Usage

```bash
# Display data as table
jn cat data.json | jn put --plugin tabulate -

# Different formats
jn cat data.json | jn put --plugin tabulate --tablefmt grid -
jn cat data.json | jn put --plugin tabulate --tablefmt psql -
jn cat data.json | jn put --plugin tabulate --tablefmt markdown -
```

**Supported formats:**
- `simple` - Clean, minimal (default)
- `grid` - Box drawing characters
- `psql` - PostgreSQL style
- `markdown` - Markdown tables
- `html` - HTML tables (future)
- 15+ formats from `tabulate` library

## Table Reading (Future Feature)

### Challenge

How to convert tables back to NDJSON?

**ASCII tables:** Ambiguous, hard to parse reliably.

**CSV/TSV:** Straightforward - already have `csv_` plugin.

**Markdown tables:** Parseable but edge cases (multi-line cells, escaped pipes).

**HTML tables:** Parseable with BeautifulSoup.

### Proposed Design

**Phase 1:** Focus on structured formats (CSV, TSV, HTML).

```bash
# HTML table → NDJSON
jn cat table.html | jn put --plugin html --mode read | ...
```

**Phase 2:** Consider ASCII table parsing if demand exists.

**Trade-offs:**
- **Pros:** Round-trip workflows, ingest tables from docs
- **Cons:** Complex parsing, ambiguous formats, edge cases
- **Decision:** Add to roadmap, implement if users request

### Roadmap Addition

```markdown
## Phase 3 (Future)

### Table Reading Plugin
- Parse HTML tables to NDJSON
- Parse Markdown tables to NDJSON
- ASCII table detection (best-effort)
- Config for column types, delimiters
```

## Format-Specific Design Patterns

### 1. Schema Inference

Some formats (CSV, tables) don't have types. Infer from data:

```python
# CSV plugin: Infer types
if value.isdigit():
    return int(value)
elif is_float(value):
    return float(value)
else:
    return value  # String
```

**Trade-off:** Convenience vs. correctness. Sometimes "123" should stay a string.

**Solution:** Config option: `--infer-types true/false`

### 2. Missing Fields

JSON objects can have different keys. CSV requires consistent columns.

```python
# Collect all keys across records
all_keys = set()
for record in records:
    all_keys.update(record.keys())

# Write CSV with all columns
writer = csv.DictWriter(sys.stdout, fieldnames=sorted(all_keys))
```

**Result:** Sparse CSV with empty cells for missing fields.

### 3. Nested Data

CSV is flat. JSON can be nested.

**Example:**
```json
{"name": "Alice", "address": {"city": "NYC", "zip": "10001"}}
```

**CSV output options:**

**Option A: Flatten**
```csv
name,address.city,address.zip
Alice,NYC,10001
```

**Option B: JSON string**
```csv
name,address
Alice,"{""city"": ""NYC"", ""zip"": ""10001""}"
```

**Option C: Error**
```
Error: CSV cannot represent nested data. Flatten with jq first.
```

**Recommendation:** Option C (fail fast). User can flatten explicitly:
```bash
jn cat data.json | jn filter '{name, city: .address.city}' | jn put out.csv
```

### 4. Arrays

How to represent arrays in CSV?

**Example:**
```json
{"name": "Alice", "hobbies": ["reading", "hiking"]}
```

**Options:**

**A: Join with delimiter**
```csv
name,hobbies
Alice,"reading,hiking"
```

**B: JSON string**
```csv
name,hobbies
Alice,"[""reading"", ""hiking""]"
```

**C: Error**
```
Error: CSV cannot represent arrays. Transform with jq first.
```

**Recommendation:** Option A with config:
```bash
jn put out.csv --array-delimiter ","
```

## Best Practices

### 1. **Fail Fast on Ambiguity**

Don't silently mangle data. If format can't represent structure, error clearly.

```python
if isinstance(value, (dict, list)):
    raise ValueError(
        "CSV cannot represent nested data. "
        "Flatten with: jn filter '{field1, field2}'"
    )
```

### 2. **Config for Edge Cases**

Provide escape hatches for power users:

```python
def writes(config: Optional[dict] = None) -> None:
    config = config or {}
    delimiter = config.get("delimiter", ",")
    infer_types = config.get("infer_types", True)
    array_delimiter = config.get("array_delimiter", None)
```

### 3. **Document Limitations**

Every format has limits. Document them clearly.

**Example: `csv_.py` docstring:**
```python
"""CSV format plugin.

Limitations:
- Cannot represent nested objects (use jq to flatten)
- Cannot represent arrays (use --array-delimiter or flatten)
- All records must have same schema (union of keys used)
- Large files buffered in memory (need all keys for header)
"""
```

### 4. **Streaming by Default**

Prefer streaming even if it's harder:

```python
# Good: Stream records one at a time
def reads(config):
    for line in sys.stdin:
        yield parse_line(line)

# Bad: Buffer entire file
def reads(config):
    data = sys.stdin.read()
    return parse_entire_file(data)
```

**Exception:** Formats that require lookahead (CSV writing needs column union).

## Related Documents

- `http-design.md` - HTTP protocol plugin
- `rest-api-profiles.md` - Profile system for APIs
- `genomoncology-api.md` - Real-world API example

## Next Steps

1. **Implement table reading** - HTML and Markdown table parsing
2. **Add flatten config** - Auto-flatten nested JSON for CSV
3. **Schema validation** - Optional JSON schema validation
4. **Type hints** - Add type annotations to format plugins
5. **Performance testing** - Benchmark large file handling
