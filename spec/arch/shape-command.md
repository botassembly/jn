# JN — Shape Command Architecture

**Status:** Design (Implementation Pending)
**Updated:** 2025-11-07
**Related:** `spec/arch/shallow-json.md` (ADR-002)

---

## Purpose

The `jn shape` command helps **LLMs and developers understand data structure efficiently** without loading entire datasets into memory or context windows.

**Core insight:** Like `head`/`tail` for content, but **structure-aware** and **streaming**.

---

## Problem: LLM Context Window Optimization

When working with data sources (files, APIs, databases), LLMs need to:

1. **Understand structure** - What fields exist? What types?
2. **See examples** - Representative sample data
3. **Avoid bloat** - Don't ingest entire datasets (token cost, memory)

**Traditional approach problems:**
- `cat file.json` - Entire file in context (expensive, slow)
- `head -n 100 file.json` - Truncates mid-record (broken JSON)
- Manual inspection - Tedious, not automatable

**Solution:** `jn shape` produces **compact, faithful artifacts** that convey structure + examples without exposing full payloads.

---

## What Shape Does

Given a data source (file, URL, source reference), `jn shape` produces three artifacts:

### 1. Profile (Statistics)
Per-field metrics and cardinality:
```json
{
  "fields": {
    "name": {
      "type": ["string"],
      "count": 1000,
      "nulls": 0,
      "examples": ["Alice", "Bob", "Charlie"],
      "string_length": {"min": 3, "avg": 8.5, "max": 24}
    },
    "age": {
      "type": ["number"],
      "count": 1000,
      "nulls": 5,
      "numeric": {"min": 18, "max": 65, "avg": 34.2}
    },
    "email": {
      "type": ["string"],
      "count": 1000,
      "format": "email",
      "cardinality": 987,
      "examples": ["alice@example.com", "bob@example.com"]
    }
  },
  "record_count": 1000
}
```

### 2. Shallow Preview (Truncated Samples)
Representative records with truncation annotations:
```json
[
  {
    "name": "Alice",
    "bio": "Software engineer who…(len=487, sha256=a3b2c1…)",
    "projects": [
      {"name": "Project A", "…": "2 more items"},
      "…(len=5)"
    ],
    "metadata": {
      "created": "2023-01-15T10:30:00Z",
      "…": "3 more keys (depth>2)"
    }
  }
]
```

**Key features:**
- Strings truncated with length + hash
- Arrays sampled (first, middle, last)
- Objects pruned by depth
- Binary/base64 replaced with metadata
- Deterministic (seeded sampling)

### 3. Inferred Schema (JSON Schema)
Machine-readable schema for validation:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["name", "email"],
  "properties": {
    "name": {"type": "string"},
    "age": {"type": ["number", "null"]},
    "email": {"type": "string", "format": "email"},
    "projects": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"}
        }
      }
    }
  }
}
```

---

## CLI Interface

### Basic Usage

```bash
# Analyze a file
jn shape --in data/users.ndjson

# Output to specific files
jn shape --in data/users.ndjson \
  --profile profile.json \
  --preview preview.json \
  --schema schema.json

# Analyze a source (from config)
jn shape --source users-api

# Configure truncation and sampling
jn shape --in data/large.ndjson \
  --truncate 50 \
  --array-sample 2,mid,2 \
  --depth 4 \
  --seed 42

# Validate stream against schema
cat new-data.ndjson | jn shape --validate schema.json
```

### Flags

```
--in <path|url>           Input file or URL to analyze
--source <name>           Analyze a configured source
--profile <path>          Output profile JSON (default: stdout)
--preview <path>          Output shallow preview JSON
--schema <path>           Output JSON Schema
--truncate <n>            Truncate strings to N chars (default: 24)
--array-sample <pattern>  Array sampling pattern (default: "1,mid,1")
--depth <n>               Max object depth (default: 3)
--seed <n>                Random seed for sampling (default: 0)
--validate <schema>       Validate input against schema
--records <n>             Process only first N records
```

---

## Use Cases

### 1. LLM-Assisted Pipeline Design

**Scenario:** Agent needs to understand API response structure

```bash
# Agent asks: "What does the GitHub API return?"
jn shape --source github-repos --preview preview.json

# Agent receives compact preview (50 lines instead of 10,000)
# Agent: "I see the 'stargazers_count' field, let me filter by that"
```

**Before:** 50KB of API response in context
**After:** 2KB preview with structure + examples

### 2. Data Source Discovery

**Scenario:** Developer has unfamiliar CSV file

```bash
jn shape --in mysterious.csv --profile profile.json

# Profile shows:
# - 50 fields
# - 1M records
# - Field types (3 dates, 12 numbers, 35 strings)
# - Cardinality (e.g., "status" has 5 unique values)
```

**Insight:** Quickly understand data without opening massive file

### 3. Schema Validation

**Scenario:** Ensure new data matches expected schema

```bash
# Infer schema from known-good data
jn shape --in prod-data.ndjson --schema prod-schema.json

# Validate new data
jn shape --in new-batch.ndjson --validate prod-schema.json
```

**Use:** Catch schema drift before pipeline failures

### 4. Documentation Generation

**Scenario:** Auto-generate data dictionaries

```bash
# Generate schema for all sources
for source in $(jn list sources); do
  jn shape --source $source --schema "docs/schemas/$source.json"
done
```

**Output:** Schema files for documentation site

---

## Architecture Integration

### Pipeline Position

`jn shape` operates **before** or **alongside** pipelines:

```
Data Source → [shape analysis] → Profile/Preview/Schema
              ↓
         Pipeline Design
              ↓
Source → Converter → Target
```

**Not** a pipeline component, but a **pipeline design tool**.

### Source Integration

```bash
# Shape can analyze any source type
jn shape --source <name>

# Internally:
# 1. Resolve source config
# 2. Run source (exec/shell/file/curl)
# 3. Capture output stream
# 4. Analyze without modifying
```

**Benefits:**
- Test sources before using in pipelines
- Validate source output format
- Generate schema for converters

---

## Implementation Strategy

See **`spec/arch/shallow-json.md` (ADR-002)** for complete implementation details.

### Key Technologies

**Parsing/streaming:**
- `ijson` - Streaming JSON parser (handles GB+ files)
- `orjson` - Fast JSON serialization

**Schema inference:**
- `genson` - Merge schemas from multiple samples
- `jsonschema` - Validation

**Statistics:**
- Welford's algorithm - Streaming mean/variance (O(1) memory)
- HyperLogLog - Cardinality estimation (`datasketch`)

**Date/format detection:**
- `python-dateutil` - Strict date parsing
- Regex patterns - email/URL/IP detection

### Streaming Architecture

**Memory guarantee:** O(1) memory regardless of input size

```python
# Pseudocode
def analyze_stream(input_stream):
    stats = {}  # Field statistics
    schema_builder = SchemaBuilder()
    sample_records = []

    for i, record in enumerate(input_stream):
        # Update statistics (O(1) per field)
        update_stats(stats, record)

        # Merge schema (O(fields) per record)
        schema_builder.add_object(record)

        # Sample records deterministically
        if should_sample(i, seed):
            sample_records.append(record)

    # Generate outputs
    profile = build_profile(stats)
    preview = build_preview(sample_records)
    schema = schema_builder.to_schema()

    return profile, preview, schema
```

**Key:** No full-dataset materialization, incremental processing

---

## Determinism & Reproducibility

**All outputs are deterministic:**

1. **Seeded sampling** - Same seed → same samples
2. **Canonical JSON** - Sorted keys (JCS-style)
3. **Fixed truncation** - Consistent string/array truncation rules
4. **Stable hashing** - SHA256 for referential identity

**Benefits:**
- Reproducible artifacts (CI/CD)
- Diffable previews (version control)
- Consistent documentation

---

## Privacy & Security

**No PII exposure:**

1. **Truncation** - Long strings truncated (names, addresses, etc.)
2. **Hashing** - Full values replaced with SHA256
3. **Optional tokenization** - Replace detected patterns
   - `[EMAIL]` for emails
   - `[PHONE]` for phone numbers
   - `[UUID]` for UUIDs

**Configuration:**
```bash
# Aggressive privacy mode
jn shape --in sensitive.json \
  --truncate 0 \
  --tokenize email,phone,ssn \
  --preview preview.json
```

**Example output:**
```json
{
  "name": "(string, len=18, sha256=…)",
  "email": "[EMAIL]",
  "ssn": "[SSN]"
}
```

---

## Testing Strategy

### Unit Tests

```python
def test_string_truncation():
    long_string = "a" * 1000
    truncated = truncate_string(long_string, max_len=24)
    assert "…(len=1000, sha256=" in truncated

def test_array_sampling():
    large_array = list(range(100))
    sampled = sample_array(large_array, pattern="2,mid,2")
    assert len(sampled) == 5  # 2 + 1 mid + 2

def test_schema_inference():
    records = [
        {"age": 30, "name": "Alice"},
        {"age": 25, "name": "Bob"},
        {"age": None, "name": "Charlie"}
    ]
    schema = infer_schema(records)
    assert schema["properties"]["age"]["type"] == ["number", "null"]

def test_deterministic_sampling():
    data = list(range(1000))
    sample1 = sample_with_seed(data, seed=42, n=10)
    sample2 = sample_with_seed(data, seed=42, n=10)
    assert sample1 == sample2  # Same seed → same sample
```

### Integration Tests

```python
def test_shape_command_file(runner, tmp_path):
    """Test jn shape with file input."""
    data_file = tmp_path / "data.ndjson"
    data_file.write_text('{"x":1}\n{"x":2}\n{"x":3}\n')

    result = runner.invoke(app, [
        "shape",
        "--in", str(data_file),
        "--profile", "profile.json",
        "--preview", "preview.json",
        "--schema", "schema.json"
    ])

    assert result.exit_code == 0
    assert (tmp_path / "profile.json").exists()
    assert (tmp_path / "preview.json").exists()
    assert (tmp_path / "schema.json").exists()

def test_shape_command_source(runner, tmp_path):
    """Test jn shape with source reference."""
    jn_path = tmp_path / "jn.json"
    init_config(runner, jn_path)

    # Create source
    add_exec_source(runner, jn_path, "test", [
        "python", "-c",
        "import json; print(json.dumps({'x': 1}))"
    ])

    # Shape the source
    result = runner.invoke(app, [
        "shape",
        "--source", "test",
        "--jn", str(jn_path)
    ])

    assert result.exit_code == 0
    assert "profile" in result.output or "schema" in result.output
```

---

## Roadmap

### Phase 1: Core Implementation ✅ (Design Complete)
- ✅ Profile generation (statistics)
- ✅ Shallow preview (truncation/sampling)
- ✅ Schema inference (JSON Schema)
- ✅ Streaming architecture (O(1) memory)
- ✅ CLI interface design

### Phase 2: Integration (Next)
- [ ] Integrate with source execution
- [ ] Add CLI command (`jn shape`)
- [ ] Implement truncation strategies
- [ ] Schema inference with genson
- [ ] Write tests

### Phase 3: Enhancements (Future)
- [ ] Privacy mode (tokenization)
- [ ] Format detection improvements (URL, UUID, etc.)
- [ ] Performance optimizations (parallel processing)
- [ ] Schema validation mode
- [ ] HTML/Markdown output formats

---

## Comparison to Alternatives

### vs `jq`
- **jq**: Transforms JSON but requires full context
- **shape**: Summarizes structure without full ingestion
- **When to use jq**: Pipeline transformations
- **When to use shape**: Understanding/exploration

### vs `head`/`tail`
- **head/tail**: Content-based truncation (breaks JSON)
- **shape**: Structure-aware truncation (valid JSON)
- **When to use head/tail**: Quick file preview
- **When to use shape**: Schema inference and sampling

### vs JSON Schema generators
- **Existing tools**: Often require full dataset in memory
- **shape**: Streaming analysis (O(1) memory)
- **Unique**: Combines profile + preview + schema

### vs `jc`
- **jc**: Source adapter (non-JSON → JSON)
- **shape**: Data profiler (JSON → insights)
- **Different purposes**: jc for ingestion, shape for exploration

---

## References

- ADR-002: `spec/arch/shallow-json.md` (complete implementation design)
- JSON Schema: https://json-schema.org/
- NDJSON: http://ndjson.org/
- JCS (JSON Canonicalization Scheme): https://tools.ietf.org/html/rfc8785
- genson (schema inference): https://github.com/wolverdude/genson
- ijson (streaming parser): https://github.com/ICRAR/ijson

---

## Summary

**`jn shape`** is a data profiling tool designed for **LLM context efficiency**:

- **Purpose:** Understand data structure without full ingestion
- **Outputs:** Profile (stats) + Preview (samples) + Schema (JSON Schema)
- **Key feature:** Structure-aware truncation with O(1) memory
- **Use cases:** Pipeline design, documentation, schema validation
- **Implementation:** See `spec/arch/shallow-json.md` for details

**Next steps:**
1. Implement core shape engine (profile + preview + schema)
2. Add `jn shape` CLI command
3. Integrate with source execution
4. Write comprehensive tests
