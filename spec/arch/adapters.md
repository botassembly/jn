# JN — Adapters (Format Boundary Handlers)

**Status:** Design / Partial Implementation
**Updated:** 2025-11-07

---

## Problem Statement

JN pipelines operate on **JSON/NDJSON streams**. The converter layer (jq) only transforms JSON → JSON. However, real-world sources often emit non-JSON formats (shell command output, CSV files, HTML, etc.), and some targets may require non-JSON input.

**Adapters** solve this by handling format boundaries:
- **Source adapters**: Convert non-JSON → JSON (at pipeline input)
- **Target adapters**: Convert JSON → non-JSON (at pipeline output)

---

## Core Principle

**Adapters ≠ Converters**

| Component | Role | Input | Output |
|-----------|------|-------|--------|
| **Converter (jq)** | Transform JSON | JSON | JSON |
| **Source Adapter** | Format ingestion | Non-JSON | JSON |
| **Target Adapter** | Format emission | JSON | Non-JSON |

**Pipeline flow:**
```
Source (raw bytes)
  ↓
[Source Adapter: non-JSON → JSON]  ← Optional
  ↓
Converter (jq: JSON → JSON)        ← Always JSON in/out
  ↓
[Target Adapter: JSON → non-JSON]  ← Optional (future)
  ↓
Target (raw bytes)
```

---

## Source Adapters

### 1. JC Adapter (Shell Output → JSON)

**What:** Wraps shell command output using [jc](https://github.com/kellyjonbrazil/jc) parsers to produce JSON.

**Use case:** Parse structured text output from CLI tools (dig, ls, ps, netstat, etc.) into JSON for jq processing.

**Two modes:**

#### A. Pipe mode (explicit)
```bash
$ dig example.com | jc --dig | jq -r '.[].answer[].data'
93.184.216.34
```

**JN equivalent:**
```json
{
  "name": "dig-lookup",
  "driver": "exec",
  "exec": {
    "argv": ["sh", "-c", "dig example.com | jc --dig"]
  }
}
```

#### B. Magic mode (registered parsers)
```bash
$ jc dig example.com | jq -r '.[].answer[].data'
93.184.216.34
```

**JN equivalent (future):**
```json
{
  "name": "dig-lookup",
  "driver": "exec",
  "exec": {
    "argv": ["jc", "dig", "example.com"]
  }
}
```

**How it works:**
- jc maintains a **registry** of command names → parser mappings
- When invoked as `jc <command> <args>`, it:
  1. Executes the command
  2. Captures stdout
  3. Applies the registered parser
  4. Emits JSON

**Supported parsers:** 80+ including dig, ls, ps, netstat, ping, route, systemctl, etc.
See: https://kellyjonbrazil.github.io/jc/docs/parsers/

---

### 2. CSV/Delimited Source (File → NDJSON)

**What:** Read CSV/TSV/delimited files and emit NDJSON (one object per row).

**Implementation approach:**
- **Option A:** Python `csv` module in a file driver
- **Option B:** External tool (csvkit's `csvjson`)
- **Option C:** jc with `--csv-s` (streaming CSV parser)

**Example with jc:**
```bash
$ cat data.csv | jc --csv-s
{"name":"Alice","age":"30"}
{"name":"Bob","age":"25"}
```

**JN config:**
```json
{
  "name": "users-csv",
  "driver": "file",
  "file": {
    "path": "users.csv",
    "format": "csv",
    "mode": "read"
  }
}
```

**Dialect options:**
- Delimiter: `,` (CSV), `\t` (TSV), custom
- Quote char: `"`
- Header handling: first row as keys
- Encoding: UTF-8, UTF-16LE/BE

---

### 3. Other Source Adapters (Future)

| Adapter | Input Format | Use Case |
|---------|--------------|----------|
| XML | XML docs | Parse RSS, config files, SOAP |
| HTML | HTML pages | Web scraping (via htmlq/pup) |
| YAML | YAML files | Config ingestion |
| Binary (Protobuf) | .proto messages | API schemas |
| Log parsers | Syslog, Apache, nginx | Structured log analysis |

---

## Target Adapters (Future)

Convert JSON to non-JSON formats when targets require specific formats.

**Examples:**

| Adapter | Output Format | Use Case |
|---------|---------------|----------|
| CSV writer | CSV files | Excel/spreadsheet export |
| Markdown table | Markdown | Documentation generation |
| HTML template | HTML | Report rendering |
| Plain text | Text formatting | Email bodies, logs |

**Design note:** Target adapters would be registered similarly to source adapters, but invoked **after** the converter stage.

---

## Registration vs. Configuration

**Registered adapters** (like jc magic mode):
- Pre-configured mappings (command → parser)
- No user config needed
- Example: `jc dig` automatically uses `--dig` parser

**Configured adapters** (like CSV with dialect):
- User specifies options (delimiter, encoding, etc.)
- Stored in source definition
- Example: CSV with custom delimiter

**Hybrid approach (recommended):**
- Registered parsers for common cases (jc, standard CSV)
- Fallback to explicit config for edge cases

---

## Implementation Strategy

### Phase 1: JC Source Adapter (Magic Mode)
1. Detect `jc` in PATH (`jn doctor` check)
2. Add `adapter: "jc"` field to source model
3. When adapter present, prepend `jc` to argv
4. Leverage jc's built-in parser registry

**Example:**
```json
{
  "name": "system-processes",
  "driver": "exec",
  "adapter": "jc",
  "exec": {
    "argv": ["ps", "aux"]
  }
}
```

**Equivalent execution:**
```bash
jc ps aux | jq '...' | target
```

### Phase 2: CSV/Delimited Source
1. Add `format: "csv"` option to file driver
2. Use jc `--csv-s` or Python csv.DictReader
3. Emit NDJSON to stdout

### Phase 3: Target Adapters
1. Design target adapter model
2. Implement CSV writer (JSON → CSV)
3. Support template engines (Jinja2) for custom formats

---

## Testing Strategy

**Source adapters:**
```bash
# Test jc adapter with registered parser
uv run jn new source ps-list --driver exec --adapter jc --argv ps aux
uv run jn run pipeline-with-ps --jn test.json

# Test CSV source
uv run jn new source users --driver file --path data.csv --format csv
uv run jn run csv-pipeline --jn test.json
```

**Integration tests:**
- Fixtures: sample CSV, shell command outputs
- Verify NDJSON output format
- Check error handling (missing jc, malformed CSV)

---

## Configuration Examples

### Complete pipeline with JC adapter

```json
{
  "sources": [
    {
      "name": "network-connections",
      "driver": "exec",
      "adapter": "jc",
      "exec": {
        "argv": ["netstat", "-an"]
      }
    }
  ],
  "converters": [
    {
      "name": "filter-established",
      "expr": ".[] | select(.state == \"ESTABLISHED\")"
    }
  ],
  "targets": [
    {
      "name": "stdout",
      "driver": "exec",
      "exec": {
        "argv": ["cat"]
      }
    }
  ],
  "pipelines": [
    {
      "name": "active-connections",
      "steps": [
        "source:network-connections",
        "converter:filter-established",
        "target:stdout"
      ]
    }
  ]
}
```

**Execution:**
```bash
jn run active-connections
# Equivalent to: jc netstat -an | jq '.[] | select(.state == "ESTABLISHED")' | cat
```

---

## Non-Goals

- **Adapters do NOT transform JSON** (that's converters)
- **Adapters do NOT implement business logic** (that's jq expressions)
- **Adapters are NOT pipelines** (they're single-purpose format handlers)

---

## Open Questions

1. Should adapters be first-class config items or just source/target options?
   - **Lean toward**: Options on sources/targets (simpler model)

2. How to handle adapter-specific errors (jc parse failure, CSV dialect mismatch)?
   - **Proposal**: Include adapter name in error envelopes

3. Should we support chaining multiple adapters?
   - **No**: Keep it simple (one adapter per source/target max)

---

## References

- jc documentation: https://kellyjonbrazil.github.io/jc/
- jc magic mode: https://github.com/kellyjonbrazil/jc#magic-syntax
- CSV handling in Python: https://docs.python.org/3/library/csv.html
- NDJSON spec: http://ndjson.org/

---

**Next steps:**
1. Implement jc adapter detection in `jn doctor`
2. Add `adapter` field to source model
3. Update `config.pipeline.run_pipeline()` to handle adapters
4. Write integration tests with jc fixtures
