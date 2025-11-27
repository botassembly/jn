# Tree-sitter + LCOV: Language-Agnostic Coverage Analysis

## Executive Summary

This spec proposes enhancements to JN that enable language-agnostic code coverage analysis by:
1. Adding a tree-sitter plugin for code structure extraction
2. Enhancing `jn join` with range/interval join support
3. Adding aggregation primitives

**Demo goal:** Run `make coverage` on the jn project, then use jn itself to analyze the coverage and identify low-coverage functions - matching the accuracy of coverage.py's HTML report.

## The Problem: Join Limitations

### Current Pain

To compute function-level coverage, we need to match **line ranges** (functions) with **individual lines** (coverage data). This is a classic **range join**:

```sql
-- What we want to express
SELECT f.function, COUNT(l.line) as total, SUM(l.executed) as hit
FROM functions f
JOIN lines l ON l.file = f.file
            AND l.line BETWEEN f.start_line AND f.end_line
GROUP BY f.function
```

**Current jn join only supports equality on single fields:**
```bash
jn join lines.json --left-key file --right-key file --target lines
```

This forces a **47-line jq workaround** to filter and aggregate:

```bash
# PAINFUL: Current workflow
jn join lines.json --left-key file --right-key file --target all_lines \
  | jq '. as $orig |
      ($orig.start_line) as $start |
      ($orig.end_line) as $end |
      {
        file: $orig.file,
        function: $orig.function,
        func_lines: [$orig.all_lines[] | select(.line >= $start and .line <= $end)]
      } | {
        file,
        function,
        total: (.func_lines | length),
        executed: ([.func_lines[] | select(.executed)] | length),
        coverage: (([.func_lines[] | select(.executed)] | length) / (.func_lines | length) * 100)
      }'
```

### Proposed Solution

**Option A: Enhanced `jn join` with `--on` syntax**

```bash
# IDEAL: One command with range join
jn join lines.json \
  --on "file = file" \
  --on "line BETWEEN start_line AND end_line" \
  --target func_lines
```

**Option B: `jn sql` command (DuckDB backend)**

```bash
# ALTERNATIVE: Full SQL power
jn sql "
  SELECT f.function,
         COUNT(l.line) as total,
         SUM(CAST(l.executed AS INT)) as hit,
         ROUND(100.0 * SUM(CAST(l.executed AS INT)) / COUNT(l.line), 1) as coverage
  FROM read_ndjson('functions.json') f
  LEFT JOIN read_ndjson('lines.json') l
    ON l.file = f.file AND l.line BETWEEN f.start_line AND f.end_line
  GROUP BY f.file, f.function
  ORDER BY coverage ASC
"
```

## Components

### 1. Tree-sitter Plugin (`ts_.py`)

Extracts code structure (functions, methods, classes) from source files using tree-sitter.

**Usage:**
```bash
jn cat "src/jn/**/*.py" --plugin ts_
```

**Output:**
```json
{"file": "src/jn/filtering.py", "function": "parse_operator", "start_line": 7, "end_line": 49}
{"file": "src/jn/filtering.py", "function": "build_jq_filter", "start_line": 149, "end_line": 210}
```

**Supported languages:** Python, JavaScript, TypeScript, Go, Rust, C/C++, Java

### 2. Enhanced LCOV Plugin

Already implemented. Add documentation for `--mode=lines`:

```bash
jn cat coverage.lcov --mode=lines
```

**Output:**
```json
{"file": "src/jn/filtering.py", "line": 7, "hits": 1, "executed": true}
{"file": "src/jn/filtering.py", "line": 35, "hits": 0, "executed": false}
```

### 3. Enhanced `jn join` (Option A)

Add `--on` syntax supporting:

| Feature | Syntax | Example |
|---------|--------|---------|
| Equality (different names) | `--on "left_field = right_field"` | `--on "customer_id = cust_id"` |
| Composite key (tuple) | `--on "f1, f2 = f1, f2"` | `--on "file, name = file, func"` |
| Range/interval | `--on "field BETWEEN start AND end"` | `--on "line BETWEEN start_line AND end_line"` |
| Comparison | `--on "field >= threshold"` | `--on "score >= min_score"` |

**Implementation:** Parse `--on` expressions and apply during join loop.

### 4. `jn sql` Command (Option B)

Wrap DuckDB for complex queries:

```bash
jn sql "SELECT * FROM read_ndjson('data.json') WHERE x > 10"
jn cat data.json | jn sql "SELECT * FROM stdin WHERE x > 10"
```

**Pros:** Full SQL power, handles any join type, aggregation built-in
**Cons:** New dependency (DuckDB ~15MB), different mental model

### 5. `jn agg` Command (Complementary)

Simple aggregation without full SQL:

```bash
jn cat data.json | jn group --by category | jn agg "sum(value), avg(score), count()"
```

## The Demo

### Setup
```bash
# Generate coverage data (already exists in jn project)
make coverage
```

### Demo Script

```bash
#!/bin/bash
# demo: Language-agnostic coverage analysis with jn

echo "=== Extract function boundaries with tree-sitter ==="
jn cat "src/jn/**/*.py" --plugin ts_ | head -3

echo ""
echo "=== Get line-level coverage from LCOV ==="
jn cat coverage.lcov --mode=lines | head -3

echo ""
echo "=== Join + aggregate to get function coverage ==="
jn cat "src/jn/**/*.py" --plugin ts_ \
  | jn join coverage.lcov~lcov?mode=lines \
      --on "file = file" \
      --on "line BETWEEN start_line AND end_line" \
      --agg "count() as total, sum(executed) as hit" \
  | jn filter '.coverage = (if .total > 0 then (.hit / .total * 100) else 0 end)' \
  | jn filter 'select(.coverage < 50)' \
  | jn filter 'sort_by(.coverage)' \
  | jn head -n 15 \
  | jn table

# Expected output (matches coverage.py HTML report):
# file                          function                   total  hit  coverage
# ─────────────────────────────────────────────────────────────────────────────
# profiles/gmail.py             load_gmail_profile           12    0      0.0%
# profiles/gmail.py             resolve_gmail_reference      12    0      0.0%
# cli/commands/vd.py            vd                           90    0      0.0%
# shell/jc_fallback.py          execute_with_jc              68    0      0.0%
# cli/commands/sh.py            sh                           36    0      0.0%
```

### Alternative Demo (DuckDB path)

```bash
#!/bin/bash
# demo: Coverage analysis with jn sql

# Prepare data
jn cat "src/jn/**/*.py" --plugin ts_ > /tmp/functions.json
jn cat coverage.lcov --mode=lines > /tmp/lines.json

# One SQL query does everything
jn sql "
  SELECT
    f.file,
    f.function,
    COUNT(l.line) as total,
    SUM(CAST(l.executed AS INT)) as hit,
    ROUND(100.0 * SUM(CAST(l.executed AS INT)) / NULLIF(COUNT(l.line), 0), 1) as coverage
  FROM read_ndjson('/tmp/functions.json') f
  LEFT JOIN read_ndjson('/tmp/lines.json') l
    ON l.file = f.file
    AND l.line BETWEEN f.start_line AND f.end_line
  GROUP BY f.file, f.function, f.start_line, f.end_line
  HAVING coverage < 50
  ORDER BY coverage ASC
  LIMIT 15
" | jn table
```

## Implementation Priority

### Phase 1: Core (MVP for demo)
1. **`ts_.py` plugin** - Tree-sitter extraction for Python
2. **Enhanced `--on` for join** - Range join support

### Phase 2: Polish
3. **`jn agg` command** - Simple aggregation
4. **Multi-language ts_** - JS, Go, Rust, etc.

### Phase 3: Power User
5. **`jn sql` command** - DuckDB integration
6. **`jn coverage` convenience** - Wraps the full pipeline

## Design Decisions

### Why Range Join in `jn join` (not just `jn sql`)?

1. **Composability:** Stays in the streaming pipeline model
2. **Familiarity:** Users already know `jn join`
3. **No new deps:** Doesn't require DuckDB
4. **Incremental:** Can add more `--on` features over time

### Why Tree-sitter (not language-specific AST)?

1. **100+ languages** with consistent API
2. **Error tolerant** - parses partial/broken code
3. **Fast** - designed for real-time editor use
4. **Single dependency** - `tree-sitter` package + language grammars

### Output Schema Consistency

All coverage tools should produce the same schema:

```json
{
  "file": "path/to/file.py",
  "function": "qualified_function_name",
  "start_line": 10,
  "end_line": 25,
  "total_statements": 12,
  "executed_statements": 8,
  "coverage": 66.67
}
```

## Success Criteria

1. **Accuracy:** Output matches coverage.py HTML report's function table
2. **Simplicity:** Demo fits in <10 lines of shell
3. **Performance:** Processes jn codebase in <5 seconds
4. **Extensibility:** Adding a new language = adding one tree-sitter grammar

## Appendix: LCOV Plugin Modes

The existing lcov plugin supports multiple output modes:

| Mode | Output | Use Case |
|------|--------|----------|
| `functions` (default) | One record per function | Function-level reports |
| `files` | One record per file | File-level summary |
| `lines` | One record per line | Join with tree-sitter |
| `branches` | One record per branch | Branch coverage analysis |

```bash
jn cat coverage.lcov                    # functions (default)
jn cat coverage.lcov --mode=lines       # for joining
jn cat coverage.lcov --mode=files       # file summary
```

## References

- [py-tree-sitter](https://github.com/tree-sitter/py-tree-sitter)
- [DuckDB read_ndjson](https://duckdb.org/docs/data/json/overview)
- [LCOV format](https://wiki.documentfoundation.org/Development/Lcov)
