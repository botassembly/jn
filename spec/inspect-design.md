# Unified Inspect Architecture

## Overview

This document specifies a unified architecture for resource inspection in JN, covering both capability discovery (what's available) and data inspection (schema, stats, facets).

## Problem Statement

The current implementation has two mechanisms:
1. `inspects()` method in protocol plugins for listing capabilities
2. No mechanism for data inspection (schema, statistics, facets)

This creates ambiguity - "inspect" means different things in different contexts. We need a unified model.

## Solution: Container vs Leaf Model

Adopt the Unix directory model:
- **Container** (no specific resource) → List what's available (like `ls`)
- **Leaf** (specific resource) → Access data (like `cat`)

**Key insight:** Container listings are just `reads()` at the container level. No separate `inspects()` method needed.

## URI Patterns

| URI Pattern | Type | Behavior |
|-------------|------|----------|
| `@api` | Container | Yield source listings as NDJSON |
| `@api/endpoint` | Leaf | Yield data records as NDJSON |
| `@api/endpoint?gene=BRAF` | Leaf + filter | Yield filtered data as NDJSON |
| `@biomcp` | Container | Yield tool/resource listings as NDJSON |
| `@biomcp/search` | Leaf | Yield tool results as NDJSON |
| `gmail://me` | Container | Yield label listings as NDJSON |
| `gmail://me/INBOX` | Leaf | Yield message records as NDJSON |
| `data.csv` | Leaf | Yield data records as NDJSON |

## Container Listing Format

All container listings use NDJSON with metadata fields:
- `_type`: Record type (e.g., "source", "tool", "resource", "label")
- `_container`: Parent container identifier

**HTTP API Sources:**
```ndjson
{"name": "alterations", "path": "/alterations", "description": "Gene alterations", "_type": "source", "_container": "@genomoncology"}
{"name": "genes", "path": "/genes", "description": "Gene database", "_type": "source", "_container": "@genomoncology"}
```

**MCP Tools:**
```ndjson
{"name": "search", "description": "Search biomedical resources", "inputSchema": {...}, "_type": "tool", "_container": "@biomcp"}
{"name": "fetch", "description": "Fetch resource data", "inputSchema": {...}, "_type": "tool", "_container": "@biomcp"}
```

**MCP Resources:**
```ndjson
{"uri": "resource://trials/NCT12345", "name": "Clinical Trial", "description": "...", "mimeType": "application/json", "_type": "resource", "_container": "@biomcp"}
```

**Gmail Labels:**
```ndjson
{"id": "INBOX", "name": "INBOX", "type": "system", "messagesTotal": 42, "messagesUnread": 5, "_type": "label", "_container": "gmail://me"}
```

## The `inspect` Command

The `inspect` command handles both container and leaf inspection with unified output formatting.

### Container Inspection

Lists available resources/tools/endpoints.

**Command:**
```bash
jn inspect @api
jn inspect @biomcp
jn inspect gmail://me
```

**Behavior:**
1. Detects this is a container (no leaf specified)
2. Calls `jn cat <container>` to get listing records
3. Aggregates NDJSON listings into structured output
4. Formats for display (text or JSON)

**Output (HTTP):**
```json
{
  "api": "genomoncology",
  "transport": "http",
  "sources": [
    {"name": "alterations", "path": "/alterations", "description": "..."},
    {"name": "genes", "path": "/genes", "description": "..."}
  ]
}
```

**Output (MCP):**
```json
{
  "server": "@biomcp",
  "transport": "stdio",
  "tools": [
    {"name": "search", "description": "...", "inputSchema": {...}}
  ],
  "resources": [
    {"uri": "resource://...", "name": "...", "description": "..."}
  ]
}
```

**Output (Gmail):**
```json
{
  "account": "me",
  "email": "user@gmail.com",
  "transport": "gmail",
  "messagesTotal": 5234,
  "threadsTotal": 2891,
  "labels": [
    {"id": "INBOX", "name": "INBOX", "type": "system", "messagesTotal": 42}
  ]
}
```

### Data Inspection

Analyzes actual data: schema, statistics, facets, samples.

**Command:**
```bash
jn inspect data.csv
jn inspect @api/alterations
jn inspect @api/alterations?gene=BRAF
jn inspect gmail://me/INBOX?from=boss
```

**Behavior:**
1. Detects this is a leaf resource
2. Separates config params from filters (via function introspection)
3. Builds pipeline: `cat --limit N [--config] | filter [expr] | analyze`
4. Returns structured metadata

**Output:**
```json
{
  "resource": "data.csv",
  "transport": "file",
  "format": "csv",
  "rows": 10000,
  "columns": 5,
  "schema": {
    "id": {
      "type": "integer",
      "nullable": false,
      "unique": 10000,
      "min": 1,
      "max": 10000
    },
    "category": {
      "type": "string",
      "nullable": false,
      "unique": 8
    },
    "revenue": {
      "type": "number",
      "nullable": true,
      "unique": 450,
      "min": 0.0,
      "max": 50000.0
    }
  },
  "facets": {
    "category": {
      "Electronics": 3500,
      "Clothing": 2500,
      "Books": 2000,
      "Home": 1500,
      "Sports": 500
    }
  },
  "stats": {
    "revenue": {
      "count": 9800,
      "nulls": 200,
      "min": 0.0,
      "max": 50000.0,
      "sum": 12345678.90,
      "mean": 1260.58,
      "variance": 202500.0,
      "stddev": 450.0
    }
  },
  "samples": {
    "first": [
      {"id": 1, "category": "Electronics", "revenue": 1200},
      {"id": 2, "category": "Clothing", "revenue": 450}
    ],
    "last": [
      {"id": 9999, "category": "Books", "revenue": 890},
      {"id": 10000, "category": "Electronics", "revenue": 2100}
    ],
    "random": [
      {"id": 3456, "category": "Home", "revenue": 750},
      {"id": 7823, "category": "Sports", "revenue": 320}
    ]
  }
}
```

## The `analyze` Command (NEW)

A new core command that reads NDJSON from stdin and outputs inspection metadata.

**Command:**
```bash
jn cat data.csv --limit 10000 | jn analyze
jn cat @api/endpoint | jn filter '.status == "active"' | jn analyze
```

**Features:**
- **Single-pass streaming** - Constant memory regardless of data size
- **Schema inference** - Detect types, nullability, cardinality
- **Automatic facet detection** - Low-cardinality fields (< 100 unique values)
- **Statistical aggregation** - Min/max/sum/mean/variance for numeric fields
- **Reservoir sampling** - Random samples without storing all records
- **First/last samples** - Track beginning and end of dataset

**Options:**
```bash
--sample-size N    Number of sample records (default: 10)
--facet-limit N    Max unique values for faceting (default: 100)
--format json|text Output format (default: json)
```

**Implementation approach:**
- Core Python command (not a plugin) for performance
- Online algorithms for statistics (no buffering)
- Automatic type inference with conflict resolution
- Track cardinality to auto-detect facet candidates

## Config vs Filter Separation

Query parameters can be either configuration (for the plugin) or filters (for data). Use function introspection to distinguish.

### Function Introspection

Extract expected parameter names from `reads()` signature:

```python
import inspect

def get_config_params(reads_func):
    """Extract config parameter names from reads() signature."""
    sig = inspect.signature(reads_func)
    params = []
    for name, param in sig.parameters.items():
        # Skip dict collectors
        if name in ('config', 'params', 'kwargs'):
            continue
        params.append(name)
    return params
```

**Example:**
```python
# http_.py
def reads(url: str, method: str = "GET", headers: dict = None,
          timeout: int = 30, verify_ssl: bool = True, **params):
    pass

get_config_params(reads)
# → ['url', 'method', 'headers', 'timeout', 'verify_ssl']
```

### Parameter Routing

```bash
jn cat '@api/endpoint?method=POST&gene=BRAF&limit=100&timeout=60'
```

**Routing logic:**
1. Load plugin's `reads()` function
2. Introspect to get config param names
3. For each query parameter:
   - If name in config params → Pass to plugin as config
   - Otherwise → Treat as data filter

**Result:**
- `method=POST`, `limit=100`, `timeout=60` → Config (passed to plugin)
- `gene=BRAF` → Filter (used to build jq expression)

### Special Case: Format Plugins

Format plugins use `config: dict` parameter:
```python
def reads(config: Optional[dict] = None):
```

For these, **all query params are config** - no filtering at `cat` level. Filters only apply via `inspect` command composition.

## Filter Building

Convert query parameters to jq filter expressions.

### Operator Parsing

Support operators in parameter names:
- `field=value` → Equality
- `field>value` → Greater than
- `field<value` → Less than
- `field>=value` → Greater than or equal
- `field<=value` → Less than or equal
- `field!=value` → Not equal

### Filter Semantics

- **Same field, multiple values** → OR
- **Different fields** → AND

**Examples:**
```bash
# OR: category equals Electronics OR Clothing
?category=Electronics&category=Clothing
# → (.category == "Electronics" or .category == "Clothing")

# AND: category equals Electronics AND revenue > 1000
?category=Electronics&revenue>1000
# → .category == "Electronics" and .revenue > 1000

# Mixed: (cat=A OR cat=B) AND revenue > 1000
?category=Electronics&category=Clothing&revenue>1000
# → (.category == "Electronics" or .category == "Clothing") and .revenue > 1000
```

### Implementation

```python
def build_jq_filter(filters: List[Tuple[str, str]]) -> str:
    """Build jq expression from filter params.

    Args:
        filters: List of (param_name, value) tuples

    Returns:
        jq filter expression
    """
    # Parse operators and group by field
    by_field = {}
    for param, value in filters:
        field, op = parse_operator(param)
        by_field.setdefault(field, []).append((op, value))

    # Build clauses
    clauses = []
    for field, conditions in by_field.items():
        if len(conditions) == 1:
            op, value = conditions[0]
            clauses.append(format_condition(field, op, value))
        else:
            # Multiple values for same field → OR
            parts = [format_condition(field, op, val) for op, val in conditions]
            clauses.append(f"({' or '.join(parts)})")

    # Combine with AND
    return " and ".join(clauses)
```

## Plugin Changes

### Protocol Plugins (http_.py, mcp_.py, gmail_.py)

**Remove:**
- `inspects()` method (no longer needed)

**Add to `reads()`:**
1. Container detection logic
2. Listing mode when container detected
3. `limit` parameter support

**Example (http_.py):**
```python
def reads(url: str, method: str = "GET", headers: dict = None,
          timeout: int = 30, verify_ssl: bool = True,
          force_format: str = None, limit: int = None, **params):
    """Read from HTTP API - handles both containers and leaves."""

    # Check if this is a container (listing) request
    if url.startswith("@"):
        ref = url[1:].split("?")[0]

        if "/" not in ref:
            # Container: @api (no endpoint)
            # Yield listing of available sources
            api_name = ref
            for source_name in list_profile_sources(api_name):
                source_profile = load_hierarchical_profile(api_name, source_name)
                yield {
                    "name": source_name,
                    "path": source_profile.get("path", ""),
                    "description": source_profile.get("description", ""),
                    "method": source_profile.get("method", "GET"),
                    "params": source_profile.get("params", []),
                    "_type": "source",
                    "_container": f"@{api_name}"
                }
            return

    # Leaf: fetch data (existing implementation)
    # ... existing code ...

    # Add limit support
    count = 0
    for record in fetch_and_parse(url, method, headers, ...):
        yield record
        if limit:
            count += 1
            if count >= limit:
                break
```

### Format Plugins (csv_.py, json_.py, etc.)

**Add:**
- `limit` parameter to `reads()` signature

**Example (csv_.py):**
```python
def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read CSV from stdin, yield NDJSON records.

    Config:
        delimiter: Field delimiter (default: ',')
        skip_rows: Number of header rows to skip (default: 0)
        limit: Maximum records to yield (default: None)
    """
    config = config or {}
    delimiter = config.get("delimiter", ",")
    skip_rows = config.get("skip_rows", 0)
    limit = config.get("limit")

    # Skip header rows
    for _ in range(skip_rows):
        next(sys.stdin, None)

    # Read CSV
    reader = csv.DictReader(sys.stdin, delimiter=delimiter)

    count = 0
    for row in reader:
        yield row
        if limit:
            count += 1
            if count >= limit:
                break
```

## New Components

### 1. Analyze Command

**Location:** `src/jn/cli/commands/analyze.py`

**Responsibilities:**
- Read NDJSON from stdin
- Infer schema (types, nullability, cardinality)
- Detect facet candidates (low-cardinality fields)
- Compute statistics (numeric fields)
- Collect samples (first, last, random via reservoir sampling)
- Output structured metadata as JSON

**Implementation:**
- `StreamingAnalyzer` class with online algorithms
- `SchemaTracker` per field
- `StatsTracker` for numeric fields
- `FacetTracker` for categorical fields
- Reservoir sampling for random samples

### 2. Function Introspection Utility

**Location:** `src/jn/introspection.py`

**Responsibilities:**
- Extract parameter names from function signatures
- Determine which query params are config vs filters

**Key functions:**
- `get_config_params(func) -> List[str]`
- `load_plugin_reads_function(plugin_path) -> callable`

### 3. Filter Building Utility

**Location:** `src/jn/filtering.py`

**Responsibilities:**
- Parse operator syntax from parameter names
- Group filters by field
- Build jq expressions with proper AND/OR logic

**Key functions:**
- `parse_operator(param: str) -> Tuple[str, str]`
- `build_jq_filter(filters: List[Tuple[str, str]]) -> str`

### 4. Updated Inspect Command

**Location:** `src/jn/cli/commands/inspect.py`

**Changes:**
- Add container detection logic
- Implement `_inspect_container()` - aggregates listings
- Implement `_inspect_data()` - builds analysis pipeline
- Update output formatting for both modes

## Implementation Plan

### Phase 1: Core Infrastructure
1. ✅ Write specification
2. Implement `analyze` command
   - StreamingAnalyzer class
   - Schema inference
   - Stats computation
   - Facet detection
   - Sample collection
3. Implement introspection utility
4. Implement filter building utility

### Phase 2: Plugin Updates
5. Update http_.py
   - Remove inspects()
   - Add container detection to reads()
   - Add limit support
6. Update mcp_.py
   - Remove inspects()
   - Add container detection to reads()
   - Add limit support
7. Update gmail_.py
   - Remove inspects()
   - Add container detection to reads()
   - Add limit support
8. Update format plugins (csv_, json_, yaml_, etc.)
   - Add limit support to reads()

### Phase 3: Command Updates
9. Update inspect command
   - Container detection
   - Container aggregation
   - Data pipeline composition
10. Update cat command (if needed for limit passing)

### Phase 4: Testing & Documentation
11. Update tests for new behavior
12. Test container listings
13. Test data inspection
14. Test filter composition
15. Update README/docs

## Success Criteria

- ✅ No `inspects()` method in any plugin
- ✅ `jn cat @api` yields listing records
- ✅ `jn inspect @api` shows formatted capabilities
- ✅ `jn inspect data.csv` shows schema/stats/facets
- ✅ `jn inspect @api/endpoint?field=value` filters and inspects
- ✅ Streaming analysis with constant memory
- ✅ All existing tests pass
- ✅ New tests for analyze command

## Benefits

1. **Unified model** - Single mechanism (`reads()`) for all resources
2. **Composable** - Listings are NDJSON, can be piped/filtered
3. **Natural** - Container/leaf matches Unix philosophy
4. **Flexible** - Raw via `cat`, formatted via `inspect`
5. **Performant** - Streaming, single-pass, constant memory
6. **Agent-friendly** - Clear separation of concerns, discoverable
