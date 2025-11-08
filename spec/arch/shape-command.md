# Shape Command

## Overview

The `shape` command analyzes NDJSON data and provides a summary: schema, sample records (head/tail), and statistics. It's designed to help users quickly understand the structure and content of their data without overwhelming them with output.

## Purpose

**Problem**: When working with large NDJSON streams, you want to know:
- What fields exist? What types are they?
- What does sample data look like?
- How many records? How big is the data?

**Solution**: `jn shape` gives you a concise summary suitable for passing to LLMs or reviewing yourself.

## Basic Usage

```bash
# Shape a file
jn cat data.csv | jn shape

# Shape API response
jn cat https://api.example.com/users | jn shape

# Shape after transformation
jn cat sales.csv | jq 'select(.amount > 100)' | jn shape
```

## Output Structure

```json
{
  "schema": {
    "type": "object",
    "properties": {
      "name": {"type": "string"},
      "age": {"type": "integer"},
      "city": {"type": "string"},
      "active": {"type": "boolean"}
    },
    "required": ["name", "age"]
  },
  "sample": {
    "head": [
      {"name": "Alice", "age": 30, "city": "NYC", "active": true},
      {"name": "Bob", "age": 25, "city": "SF", "active": false},
      {"name": "Charlie", "age": 35, "city": "Austin", "active": true},
      {"name": "Diana", "age": 28, "city": "Seattle", "active": true},
      {"name": "Eve", "age": 32, "city": "Boston", "active": false}
    ],
    "tail": [
      {"name": "Zara", "age": 29, "city": "Portland", "active": true},
      {"name": "Yuri", "age": 31, "city": "Denver", "active": false},
      {"name": "Xavier", "age": 27, "city": "Miami", "active": true},
      {"name": "Wendy", "age": 33, "city": "Phoenix", "active": false},
      {"name": "Victor", "age": 26, "city": "Nashville", "active": true}
    ]
  },
  "stats": {
    "record_count": 1000,
    "field_names": ["name", "age", "city", "active"],
    "total_chars": 45678,
    "total_tokens": 12345,
    "avg_record_size": 45
  }
}
```

## Options

```bash
# Number of sample records
jn shape --head 5 --tail 5       # Default
jn shape --head 10 --tail 10     # More samples

# Truncation limits
jn shape --max-record-chars 500  # Max chars per record (default: 500)
jn shape --max-string-length 100 # Max chars per string field (default: 100)

# Output format
jn shape --pretty                # Pretty-print JSON (default)
jn shape --compact               # Compact JSON

# Statistics
jn shape --no-tokens             # Skip token counting (faster)
jn shape --no-schema             # Skip schema inference (faster)
```

## Schema Inference

Uses **genson** library to infer JSON Schema from sample data.

```python
from genson import SchemaBuilder

builder = SchemaBuilder()

# Add records to builder
for record in records:
    builder.add_object(record)

# Generate schema
schema = builder.to_schema()
```

**Features**:
- Infers types (string, number, boolean, null, array, object)
- Detects required vs optional fields
- Handles nested objects and arrays
- Merges schemas from multiple records to find union type

**Example**:

Input records:
```json
{"name": "Alice", "age": 30}
{"name": "Bob", "city": "SF"}
```

Inferred schema:
```json
{
  "type": "object",
  "properties": {
    "name": {"type": "string"},
    "age": {"type": "integer"},
    "city": {"type": "string"}
  },
  "required": ["name"]
}
```

## Sample Records (Head/Tail)

### Head
First N records (default: 5)

### Tail
Last N records (default: 5)

**Implementation**: Buffer last N records while streaming.

```python
from collections import deque

head = []
tail = deque(maxlen=tail_size)

for i, record in enumerate(records):
    # Collect head
    if i < head_size:
        head.append(record)

    # Always add to tail (auto-evicts oldest)
    tail.append(record)
```

### Truncation

To keep output concise, truncate records if they exceed limits:

**1. Record-level truncation** (`--max-record-chars`):

If serialized record exceeds limit, drop fields until under limit:

```python
def truncate_record(record, max_chars=500):
    while len(json.dumps(record)) > max_chars and record:
        # Drop fields one by one (prioritize keeping name/id fields)
        record.pop(next(reversed(record)))
    return record
```

**2. String-level truncation** (`--max-string-length`):

Truncate long string values:

```python
def truncate_strings(record, max_length=100):
    for key, value in record.items():
        if isinstance(value, str) and len(value) > max_length:
            record[key] = value[:max_length] + "..."
    return record
```

**3. Nested object truncation**:

For nested objects, show `{...}` placeholder:

```python
def truncate_nested(record, depth=1):
    if depth > 1:
        for key, value in record.items():
            if isinstance(value, dict):
                record[key] = "{...}"
            elif isinstance(value, list):
                record[key] = "[...]"
    return record
```

**Example**:

Original record (800 chars):
```json
{
  "id": "abc123",
  "name": "Alice Johnson",
  "email": "alice.johnson@example.com",
  "bio": "Lorem ipsum dolor sit amet, consectetur adipiscing elit... (500 chars)",
  "address": {"street": "123 Main St", "city": "NYC", "state": "NY", "zip": "10001"},
  "tags": ["engineering", "management", "python", "javascript", "golang"]
}
```

Truncated record (under 500 chars):
```json
{
  "id": "abc123",
  "name": "Alice Johnson",
  "email": "alice.johnson@example.com",
  "bio": "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore...",
  "address": "{...}",
  "tags": "[...]"
}
```

## Statistics

### Record Count
Total number of records in stream.

### Field Names
List of all unique field names encountered across all records.

```python
field_names = set()
for record in records:
    field_names.update(record.keys())
```

### Total Characters
Sum of serialized length of all records.

```python
total_chars = sum(len(json.dumps(record)) for record in records)
```

### Total Tokens (Optional)
Estimated token count for LLM context.

Uses **tiktoken** library:

```python
import tiktoken

encoding = tiktoken.encoding_for_model("gpt-4")

total_tokens = 0
for record in records:
    text = json.dumps(record)
    total_tokens += len(encoding.encode(text))
```

**Note**: Token counting is expensive. Skip with `--no-tokens` for faster analysis.

### Average Record Size
Average character count per record.

```python
avg_record_size = total_chars / record_count
```

## Use Cases

### Use Case 1: Understand API Response

```bash
jn cat https://api.example.com/users | jn shape

# Quick summary of:
# - What fields does the API return?
# - What do sample records look like?
# - How many users in the response?
```

### Use Case 2: Explore Large Dataset

```bash
jn cat large-file.csv | jn shape

# Without loading entire file into memory, get:
# - Schema overview
# - First/last records
# - Total record count
```

### Use Case 3: Validate Transformation

```bash
jn cat raw-data.csv | jq 'select(.valid)' | jn shape

# Verify:
# - Filtering worked correctly
# - Expected fields remain
# - Sample output looks correct
```

### Use Case 4: LLM Context Preparation

```bash
jn cat data.csv | jn shape > data-summary.json

# Pass summary to LLM instead of full data:
# - Describe the data structure
# - Ask LLM to write jq query
# - LLM sees schema + samples without all data
```

### Use Case 5: Quick Data Profiling

```bash
# Profile multiple datasets
for file in data/*.csv; do
  echo "=== $file ==="
  jn cat "$file" | jn shape --compact
done
```

## Implementation Notes

### Streaming Architecture

```python
def shape(input_stream, head_size=5, tail_size=5, max_record_chars=500):
    from genson import SchemaBuilder
    from collections import deque
    import tiktoken

    builder = SchemaBuilder()
    head = []
    tail = deque(maxlen=tail_size)
    field_names = set()
    record_count = 0
    total_chars = 0
    total_tokens = 0
    encoding = tiktoken.encoding_for_model("gpt-4")

    for i, record in enumerate(input_stream):
        # Schema inference
        builder.add_object(record)

        # Head collection
        if i < head_size:
            truncated = truncate_record(record.copy(), max_record_chars)
            head.append(truncated)

        # Tail collection (always)
        truncated = truncate_record(record.copy(), max_record_chars)
        tail.append(truncated)

        # Statistics
        field_names.update(record.keys())
        record_json = json.dumps(record)
        total_chars += len(record_json)
        total_tokens += len(encoding.encode(record_json))
        record_count += 1

    return {
        "schema": builder.to_schema(),
        "sample": {
            "head": head,
            "tail": list(tail)
        },
        "stats": {
            "record_count": record_count,
            "field_names": sorted(field_names),
            "total_chars": total_chars,
            "total_tokens": total_tokens,
            "avg_record_size": total_chars // record_count if record_count > 0 else 0
        }
    }
```

### CLI Command

```python
import typer
from typing import Optional

@app.command()
def shape(
    head: int = 5,
    tail: int = 5,
    max_record_chars: int = 500,
    max_string_length: int = 100,
    pretty: bool = True,
    no_tokens: bool = False,
    no_schema: bool = False,
):
    """Analyze NDJSON stream and show schema, samples, and statistics"""

    # Read NDJSON from stdin
    records = read_ndjson_from_stdin()

    # Analyze
    result = shape_analysis(
        records,
        head_size=head,
        tail_size=tail,
        max_record_chars=max_record_chars,
        include_tokens=not no_tokens,
        include_schema=not no_schema,
    )

    # Output
    if pretty:
        typer.echo(json.dumps(result, indent=2))
    else:
        typer.echo(json.dumps(result))
```

## Performance Considerations

**Memory usage**:
- Schema builder: ~1KB per unique schema element
- Head/tail buffers: ~(head_size + tail_size) * max_record_chars
- Field names: ~50 bytes per unique field name

**Typical memory**: ~100KB for most datasets

**Processing speed**:
- Without tokens: ~100K records/sec
- With tokens: ~10K records/sec (tokenization is slow)

**Recommendation**: Use `--no-tokens` for large datasets (>100K records) if you don't need token counts.

## Dependencies

```toml
[tool.poetry.dependencies]
genson = "^1.2.0"       # JSON Schema inference
tiktoken = "^0.5.0"     # Token counting (optional)
```

## Example Output

```bash
$ jn cat users.csv | jn shape
```

```json
{
  "schema": {
    "type": "object",
    "properties": {
      "id": {"type": "integer"},
      "name": {"type": "string"},
      "email": {"type": "string"},
      "age": {"type": "integer"},
      "active": {"type": "boolean"},
      "created_at": {"type": "string"}
    },
    "required": ["id", "name", "email"]
  },
  "sample": {
    "head": [
      {"id": 1, "name": "Alice", "email": "alice@example.com", "age": 30, "active": true, "created_at": "2024-01-15"},
      {"id": 2, "name": "Bob", "email": "bob@example.com", "age": 25, "active": false, "created_at": "2024-01-16"},
      {"id": 3, "name": "Charlie", "email": "charlie@example.com", "age": 35, "active": true, "created_at": "2024-01-17"},
      {"id": 4, "name": "Diana", "email": "diana@example.com", "age": 28, "active": true, "created_at": "2024-01-18"},
      {"id": 5, "name": "Eve", "email": "eve@example.com", "age": 32, "active": false, "created_at": "2024-01-19"}
    ],
    "tail": [
      {"id": 996, "name": "Zara", "email": "zara@example.com", "age": 29, "active": true, "created_at": "2025-01-10"},
      {"id": 997, "name": "Yuri", "email": "yuri@example.com", "age": 31, "active": false, "created_at": "2025-01-11"},
      {"id": 998, "name": "Xavier", "email": "xavier@example.com", "age": 27, "active": true, "created_at": "2025-01-12"},
      {"id": 999, "name": "Wendy", "email": "wendy@example.com", "age": 33, "active": false, "created_at": "2025-01-13"},
      {"id": 1000, "name": "Victor", "email": "victor@example.com", "age": 26, "active": true, "created_at": "2025-01-14"}
    ]
  },
  "stats": {
    "record_count": 1000,
    "field_names": ["active", "age", "created_at", "email", "id", "name"],
    "total_chars": 89450,
    "total_tokens": 24567,
    "avg_record_size": 89
  }
}
```

## Related Commands

### `explain`

**Purpose**: Show the resolved plan for a pipeline without executing it.

**Usage**:
```bash
jn explain my-pipeline

# With details
jn explain my-pipeline --show-commands --show-env
```

**Output**: JSON representation of the pipeline execution plan:
```json
{
  "source": {
    "driver": "file",
    "path": "data.csv",
    "parser": "csv"
  },
  "converter": {
    "query": "select(.amount > 100)"
  },
  "target": {
    "driver": "file",
    "path": "output.json",
    "format": "json"
  }
}
```

**Use case**: Debug pipelines, understand what would execute before running.

### Comparison

| Command | Purpose | Input | Output |
|---------|---------|-------|--------|
| `explain` | Show pipeline plan | Pipeline config | Execution plan (JSON) |
| `shape` | Analyze data structure | NDJSON stream | Schema + samples + stats |

## Future Enhancements

**Phase 2** (not in initial implementation):
- Histogram of field value distributions
- Detect patterns (email, URL, date formats)
- Suggest jq queries based on schema
- Compare shapes of two datasets
- HTML report output

## Success Criteria

- [x] Infers JSON Schema from NDJSON stream
- [x] Shows head and tail samples (configurable count)
- [x] Truncates records to keep output concise
- [x] Computes statistics (count, fields, chars, tokens)
- [x] Streams data (low memory usage)
- [x] Works with any NDJSON source (cat, API, transformations)
- [x] Output suitable for LLM context
- [x] Test coverage >85%
