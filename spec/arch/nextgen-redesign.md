# JN (Junction): Agent-Native ETL with JSON Pipelines

**Version:** 4.0
**Date:** 2025-11-09
**Status:** Final Architecture

---

## Why JN Exists

### The Problem: Agents Need Better Data Plumbing

Language models excel at generating code but struggle with brittle text parsing. When an agent needs to:
- Extract data from APIs, databases, files, or command output
- Transform it through multiple steps
- Load it somewhere else

...they face two bad options:

1. **Write bespoke scripts** - Every ETL task becomes a one-off Python/shell script. No reuse, no standards, brittle parsing.
2. **Use heavyweight frameworks** - Airflow, Prefect, etc. require infrastructure and are too complex for simple data movement.

### The Insight: JSON + Unix Pipes + Agent-Discoverable Tools

Kelly Brazil showed us the way: **JSON as the universal data interchange format on the command line**. His work (JC, jtbl, jello) proves that:
- Legacy text output can be normalized to JSON
- JSON Lines (NDJSON) enables streaming pipelines
- Flat schemas with predictable keys make filtering trivial
- jq becomes the universal transform language

**JN extends this philosophy for agents:**

1. **Registry-free discovery** - Agents find tools by scanning the filesystem, not loading Python modules
2. **Function-based plugins** - Duck-typed hooks, not class hierarchies
3. **Automatic composition** - The framework wires together sources → filters → targets based on file extensions, URLs, and filter names
4. **Subprocess isolation** - Every plugin runs in its own UV-managed environment
5. **JSON-first schemas** - Everything speaks NDJSON, documented and testable

### The Goal

**Make ETL tool creation so simple that agents can do it on the fly.**

An agent should be able to:
```bash
# Discover what's available
jn discover

# See examples without running code
jn show csv_reader --examples

# Compose a pipeline automatically
jn run sales.csv high-value summary.xlsx

# Create a new filter
jn create filter high-value --query 'select(.amount > 1000)'

# Test it immediately
jn test high-value < test-data.ndjson
```

No Python imports. No class definitions. No config files required. Just files on disk that agents can read, modify, and compose.

---

## Core Philosophy

### 1. JSON Lines Everywhere

Every component:
- **Reads** NDJSON from stdin
- **Writes** NDJSON to stdout
- Follows Kelly Brazil's design principles: flat schemas, lower_snake_case keys, type fields for mixed streams, separate metadata

### 2. Discoverable Without Execution

Inspired by Anthropic's MCP→code proposal: **Tools are files on disk with parseable headers.**

An agent can:
- `ls ~/.jn/plugins/*.py` to list available tools
- Parse metadata from file headers (regex, no imports)
- Read example code without executing anything
- Generate new tools from templates

### 3. Automatic Pipeline Construction

The core runner is smart:
```bash
# Agent writes:
jn run data.csv filter1 filter2 output.xlsx

# JN detects:
# - data.csv → csv_reader (file extension)
# - filter1 → jq filter (registry lookup)
# - filter2 → jq filter (registry lookup)
# - output.xlsx → xlsx_writer (file extension)

# JN executes:
# csv_reader < data.csv | jq 'filter1' | jq 'filter2' | xlsx_writer > output.xlsx
```

Agents specify **what**, not **how**.

### 4. Function-Based Plugins (Duck Typing)

No inheritance. A valid plugin is any Python file with:
```python
# META: type=filter, version=1.0.0

def run(input_stream):
    """Required: Process NDJSON stream."""
    for line in input_stream:
        record = json.loads(line)
        # transform
        yield transformed_record

def examples():
    """Optional: Return runnable examples."""
    return [{
        "input": '{"amount": 500}\n{"amount": 1500}',
        "output": '{"amount": 1500}',
        "description": "Filters records with amount > 1000"
    }]
```

If it has `run()`, it's a plugin. Everything else is optional conventions.

### 5. UV-Powered Subprocess Isolation

Every plugin declares dependencies in PEP 723 format:
```python
# /// script
# dependencies = ["pandas>=2.0.0", "requests>=2.28.0"]
# ///
```

JN executes via `uv run plugin.py`, ensuring:
- No global dependency conflicts
- Fast caching (UV reuses envs)
- Agents can add dependencies freely

---

## Component Types

### Sources

**Purpose:** Extract data from external systems and convert to NDJSON.

**Required function:** `run(config: dict) → Iterator[dict]`

**Common types:**
- **Readers:** File format converters (CSV→NDJSON, JSON→NDJSON, Excel→NDJSON)
- **Fetchers:** HTTP APIs, databases, S3, message queues
- **Parsers:** Shell command output (via JC integration)

**Example metadata:**
```python
# META: type=source, handles=[".csv", ".tsv"], schema=csv_record
```

**Schema convention:** Document output structure in docstring or separate `.schema.json` file.

### Filters

**Purpose:** Transform NDJSON → NDJSON.

**Required function:** `run(input_stream: Iterator[str]) → Iterator[dict]`

**Common types:**
- **jq wrappers:** Most filters just call jq with a query
- **Python transforms:** When jq isn't expressive enough (date parsing, regex, aggregations)
- **Aggregators:** Group-by, pivot, window functions

**Example metadata:**
```python
# META: type=filter, streaming=true
```

**Streaming vs. buffering:** Metadata indicates if filter must read entire stream (aggregations) or can process line-by-line (most transforms).

### Targets

**Purpose:** Load NDJSON into external systems.

**Required function:** `run(input_stream: Iterator[dict], config: dict) → None`

**Common types:**
- **Writers:** NDJSON→file formats (CSV, JSON, Excel, Parquet)
- **Senders:** HTTP POST, database INSERT, S3 upload, message queue publish
- **Displayers:** Table formatters (jtbl integration), charts, reports

**Example metadata:**
```python
# META: type=target, handles=[".xlsx", ".csv"]
```

---

## Discovery System

### Plugin Locations

JN scans (in order):
1. `./.jn/plugins/` (project-local)
2. `~/.jn/plugins/` (user global)
3. `/usr/local/share/jn/plugins/` (system-wide)

### Registration Without Imports

**Agent workflow:**
```python
# Agent lists plugins
files = glob("~/.jn/plugins/*.py")

# Agent parses metadata (regex, no execution)
for file in files:
    content = file.read_text()
    if match := re.search(r'# META: type=(\w+), handles=\[(.*?)\]', content):
        register(file.stem, type=match[1], extensions=match[2])
```

**No Python imports = no dependency loading = fast discovery.**

### Schema Files (Optional)

```
~/.jn/plugins/
  csv_reader.py
  csv_reader.schema.json   # Optional: JSON Schema for output
  csv_reader.examples.json # Optional: Test cases
```

Agents can read schemas to understand data shapes without running code.

### Modification Time Tracking

JN caches plugin metadata with file modification times. Agents can:
```bash
jn discover --changed-since "2025-11-08"
```

Only re-scans plugins modified after timestamp (the user's requirement about "date checking").

---

## Automatic Pipeline Construction

### The Core Runner

```bash
jn run <input> [<filter>...] <output>
```

**Detection logic:**

1. **Input detection:**
   - URL pattern (`https://...`) → HTTP fetcher
   - File exists + extension (`.csv`) → registry lookup → `csv_reader`
   - Command name (`dig example.com`) → JC parser

2. **Filter detection:**
   - Name exists in filter registry → jq wrapper
   - Inline jq expression (starts with `.` or `select(`) → ephemeral jq

3. **Output detection:**
   - File extension (`.xlsx`) → registry lookup → `xlsx_writer`
   - Stdout (`-`) → JSON Lines to terminal
   - URL (`https://api.example.com/upload`) → HTTP POST

**Example automatic construction:**
```bash
# Agent types:
jn run sales.csv 'select(.amount > 1000)' summary.xlsx

# JN constructs:
csv_reader < sales.csv \
  | jq 'select(.amount > 1000)' \
  | xlsx_writer > summary.xlsx
```

### Extension Registry

**Format:** Simple JSON file
```json
{
  "extensions": {
    ".csv": {"read": "csv_reader", "write": "csv_writer"},
    ".xlsx": {"read": "xlsx_reader", "write": "xlsx_writer"},
    ".parquet": {"read": "parquet_reader", "write": "parquet_writer"}
  },
  "url_patterns": {
    "https://api.github.com/": "github_fetcher"
  }
}
```

Agents can modify this file to register new handlers.

---

## Agent-Friendly CLI

### Discovery Commands

```bash
# List all available plugins
jn discover [--type=source|filter|target]

# Show plugin details (read from file, don't execute)
jn show csv_reader

# Show examples (read from file or docstring)
jn show csv_reader --examples

# Show schema (read .schema.json if exists)
jn show csv_reader --schema

# Find plugins by capability
jn find --reads csv --writes excel
```

### Creation Commands

```bash
# Create new filter from template
jn create filter high-value \
  --query 'select(.amount > 1000)' \
  --description "Filter high-value transactions"

# Create new source from template
jn create source api-fetch \
  --template http-json \
  --url https://api.example.com/data

# Validate plugin (lint + dry-run)
jn validate high-value
```

### Testing Commands

```bash
# Run examples from plugin
jn test high-value

# Test with custom input
jn test high-value < test-data.ndjson

# Test entire pipeline
jn test sales.csv high-value summary.xlsx --dry-run
```

### Execution Commands

```bash
# Automatic pipeline
jn run <input> [<filter>...] <output>

# Explicit components (override detection)
jn run --source csv_reader --in data.csv \
       --filter high-value \
       --target xlsx_writer --out result.xlsx

# Interactive exploration
jn cat data.csv | head -10  # Preview first 10 records
jn cat https://api.github.com/users/octocat | jq '.login'
```

---

## Plugin Template Structure

### Minimal Filter Example

```python
#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
# META: type=filter, streaming=true

import json
import sys

def run(input_stream):
    """Filter records where amount > 1000."""
    for line in input_stream:
        record = json.loads(line)
        if record.get('amount', 0) > 1000:
            yield record

if __name__ == '__main__':
    for record in run(sys.stdin):
        print(json.dumps(record))
```

**That's it.** 19 lines. No classes, no base imports, just a function.

### With Examples (Runnable Tests)

```python
def examples():
    """Return test cases."""
    return [
        {
            "description": "Filters records with amount > 1000",
            "input": [
                {"amount": 500, "id": 1},
                {"amount": 1500, "id": 2}
            ],
            "expected": [
                {"amount": 1500, "id": 2}
            ]
        }
    ]

def test():
    """Run examples as tests."""
    for example in examples():
        input_ndjson = '\n'.join(json.dumps(r) for r in example['input'])
        output = list(run(input_ndjson.splitlines()))
        assert output == example['expected'], f"Test failed: {example['description']}"
    print("All tests passed!")
```

Agents can:
- Read `examples()` to understand behavior
- Run `python filter.py --test` to validate
- Generate new examples when modifying

---

## Integration with Kelly Brazil's Tooling

### JC Integration (Built-in)

JN ships with JC adapters:
```bash
# Agent types:
jn run 'dig example.com' extract-ips report.csv

# JN executes:
dig example.com | jc --dig | jq '.[] | .answer[] | .data' | csv_writer
```

All JC parsers available as sources automatically.

### jtbl Integration (Optional)

```bash
# Quick visualization during development
jn cat data.csv | jtbl

# Or as a target
jn run data.csv filter1 - | jtbl
```

### Schema Conventions (Kelly Brazil Style)

All JN plugins follow the same design principles:
- **Flat schemas:** Avoid deep nesting
- **Predictable keys:** `lower_snake_case`, no special chars
- **Type fields:** Mixed streams include `_type`
- **Metadata separation:** Optional `_meta` field for provenance
- **Timestamp consistency:** Include both `timestamp` (ISO) and `timestamp_epoch`
- **Number safety:** Large IDs as strings

---

## Framework Benefits for Agents

### 1. Token Efficiency

**Without JN:** Agent must include full function definitions in context
```python
# Agent writes 50+ lines of pandas/requests code
import pandas as pd
import requests
# ... full implementation
```

**With JN:** Agent references file on disk
```bash
jn run sales.csv high-value summary.xlsx
```

Zero tokens for tool definitions. Agent only needs to know tool names.

### 2. Discoverability

```bash
# Agent can ask:
jn discover --type filter

# Output:
# high-value - Filter records with amount > 1000
# active-only - Select only active records
# dedupe - Remove duplicate records by ID
```

No tool descriptions in context. Agent queries filesystem as needed.

### 3. Composability

Agents wire together tools without round-tripping data:
```bash
# Data never enters LLM context
jn run large-dataset.csv \
  complex-transform \
  sensitive-filter \
  secure-upload.sh
```

Data flows through Unix pipes. LLM only orchestrates.

### 4. Modifiability

Agent can create/modify tools:
```python
# Agent generates new filter
filter_code = generate_filter_from_spec(user_requirements)
Path("~/.jn/plugins/custom_filter.py").write_text(filter_code)

# Immediately available
subprocess.run(["jn", "test", "custom_filter"])
subprocess.run(["jn", "run", "data.csv", "custom_filter", "output.json"])
```

### 5. Reliability

Each plugin has examples. Agent can:
- Read examples to understand behavior
- Generate test data that matches schemas
- Validate pipelines before running on real data

---

## Comparison to Other Approaches

### vs. Ad-hoc Scripts
| Aspect | Ad-hoc | JN |
|--------|--------|-----|
| Reuse | ❌ Every task is unique | ✅ Plugins compose freely |
| Discovery | ❌ Agent must search codebase | ✅ `jn discover` |
| Testing | ❌ Manual validation | ✅ Built-in `--test` |
| Isolation | ❌ Global dependencies | ✅ UV per-plugin envs |

### vs. Heavyweight ETL Frameworks
| Aspect | Airflow/Prefect | JN |
|--------|-----------------|-----|
| Setup | ❌ Requires infrastructure | ✅ Just install jn |
| Learning curve | ❌ Steep | ✅ Shallow (Unix pipes + JSON) |
| Agent-friendly | ❌ Complex APIs | ✅ Simple CLI |
| Overhead | ❌ Scheduler, DB, workers | ✅ Direct execution |

### vs. MCP Tools (Traditional)
| Aspect | MCP | JN |
|--------|-----|-----|
| Context overhead | ❌ All tools in context | ✅ Zero (files on disk) |
| Data flow | ❌ Through LLM | ✅ Unix pipes |
| Discoverability | ⚠️ List all tools | ✅ Query as needed |
| Execution | ✅ RPC calls | ✅ Subprocess |

### The MCP→Code Insight Applied

JN takes Anthropic's MCP→code execution concept further:

**MCP approach:** Generate TypeScript wrapper functions
```typescript
export async function getDocument(input: GetDocumentInput) {
  return callMCPTool('google_drive__get_document', input);
}
```

**JN approach:** Plugins ARE the functions
```python
# ~/.jn/plugins/gdrive_get.py
def run(config):
    doc = gdrive_client.get(config['document_id'])
    yield {'content': doc.content, 'id': doc.id}
```

No wrapper layer. Direct execution. Data never touches LLM context.

---

## Implementation Priorities

### Phase 1: Core Runner (Week 1-2)
- Plugin discovery (filesystem scan + regex)
- Automatic pipeline construction
- Extension registry
- UV subprocess execution
- `jn run` command

### Phase 2: Essential Plugins (Week 3-4)
- csv_reader / csv_writer
- json_reader / json_writer (pass-through)
- jq_filter (wrapper)
- http_get / http_post
- JC integration (shell commands)

### Phase 3: Agent Tools (Week 5-6)
- `jn discover`, `jn show`, `jn find`
- `jn create` (template-based plugin generation)
- `jn test` (run examples)
- `jn validate` (lint + dry-run)

### Phase 4: Advanced Features (Week 7-8)
- Schema file support
- jtbl integration
- Advanced readers (Excel, Parquet)
- Database connectors
- Streaming aggregations

---

## Success Metrics

**JN succeeds when:**

1. **Agent can create a working ETL pipeline in one prompt:**
   ```
   User: "Pull sales data from CSV, filter for amounts > 1000, save to Excel"
   Agent: jn run sales.csv 'select(.amount > 1000)' summary.xlsx
   ```

2. **Agent can extend JN without human help:**
   ```
   Agent: jn create filter complex-transform --from template
   Agent: # edits filter code
   Agent: jn test complex-transform
   Agent: jn run data.csv complex-transform output.json
   ```

3. **Plugins are self-documenting:**
   ```
   Agent: jn show csv_reader --examples
   Agent: # reads examples, understands schema
   Agent: # generates compatible jq filter
   ```

4. **Data never enters LLM unnecessarily:**
   - Agents orchestrate, Unix pipes move data
   - Context contains tool names, not tool definitions
   - Large datasets flow through without touching model

---

## Design Principles Summary

1. **JSON Lines everywhere** - Universal interchange format
2. **Functions, not classes** - Duck typing, minimal ceremony
3. **Discoverable without execution** - Metadata in file headers
4. **Automatic composition** - Smart detection from extensions/URLs
5. **UV-powered isolation** - No dependency conflicts
6. **Examples as tests** - Documentation that runs
7. **Agent-first CLI** - Designed for programmatic use
8. **Kelly Brazil principles** - Flat schemas, predictable keys, NDJSON streaming
9. **Zero-context tooling** - Tools live on filesystem, not in LLM memory
10. **Framework over ad-hoc** - Reusable components, not one-off scripts

---

## Conclusion

**JN makes JSON pipelines as composable as Unix pipes.**

For agents, this means:
- **Discover** tools by listing files
- **Understand** tools by reading examples
- **Compose** tools automatically based on inputs/outputs
- **Create** new tools from templates
- **Test** everything before running
- **Execute** without data touching the LLM

The result: **ETL becomes a language agents can speak fluently.**

No more brittle text parsing. No more one-off scripts. No more heavyweight frameworks.

Just clean JSON pipelines that agents can build, test, and modify on the fly.
