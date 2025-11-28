# Code Analysis Plugin Design

## Problem

Analyzing code coverage at the function level requires correlating two data sources:
1. **Code structure** - Function names, line ranges, class membership
2. **Coverage data** - Which lines were executed (LCOV format)

Existing tools either report file-level coverage or require language-specific tooling. We need a language-agnostic solution that integrates with jn's streaming pipeline.

## Design Goals

1. **Language-agnostic** - Single plugin handles Python, JS, Go, Rust via tree-sitter
2. **Streaming** - Output NDJSON records as they're extracted, don't buffer
3. **Composable** - Works with jn filter, table, vd for analysis
4. **Coverage-optional** - Structure extraction works without LCOV data

## Architecture

```
@code/functions?root=src&lcov=coverage.lcov
       │
       ▼
┌─────────────────────────────────────────┐
│           code_.py plugin               │
├─────────────────────────────────────────┤
│  1. Find files (glob patterns)         │
│  2. Detect language (extension)        │
│  3. Parse with tree-sitter             │
│  4. Extract functions/classes/calls    │
│  5. Enrich with coverage (if lcov)     │
│  6. Enrich with caller_count           │
└─────────────────────────────────────────┘
       │
       ▼
   NDJSON stream
```

## Components

### Address Format

```
@code/<component>?<params>
```

| Component | Description |
|-----------|-------------|
| `functions` | All functions with caller_count, optional coverage |
| `classes` | Class definitions only |
| `methods` | Methods (functions inside classes) |
| `calls` | Caller → callee relationships |
| `dead` | Functions with no callers (false-positive filtered) |
| `files` | Just list matching files |

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `root` | `.` | Source directory to scan |
| `globs` | `**/*.py` | Comma-separated glob patterns |
| `lcov` | none | LCOV file path for coverage enrichment |
| `min` | 0 | Minimum coverage % filter |
| `max` | 100 | Maximum coverage % filter |
| `type` | none | Filter by type: function, method, class |

## Language Support

Each language has dedicated extractors using tree-sitter queries:

| Language | Extensions | Functions | Classes | Calls |
|----------|------------|-----------|---------|-------|
| Python | `.py` | ✅ | ✅ | ✅ |
| JavaScript | `.js`, `.ts`, `.jsx`, `.tsx` | ✅ | ✅ | ✅ |
| Go | `.go` | ✅ | ✅ (structs) | ✅ |
| Rust | `.rs` | ✅ | ✅ (impl) | ✅ |

### Body Detection

Functions use tree-sitter's `body` field for language-agnostic line range detection:

```python
def get_body_range(node):
    """Get body line range using tree-sitter's body field."""
    body = node.child_by_field_name('body')
    if body:
        return body.start_point[0] + 1, body.end_point[0] + 1
    return node.start_point[0] + 1, node.end_point[0] + 1
```

## Coverage Enrichment

When `lcov` parameter is provided:

1. Parse LCOV file into `{file: {line: hit_count}}` lookup
2. For each function, count lines in body range
3. Calculate `coverage = (hit_lines / total_lines) * 100`

Output fields added:
- `lines` - Total lines in function body
- `hit` - Lines executed at least once
- `coverage` - Percentage (0-100)

## Call Graph

The `@code/calls` component extracts caller → callee relationships:

```json
{"caller": "parse_address", "callee": "_validate_address", "file": "parser.py"}
```

Used to compute `caller_count` for dead code detection.

### Dead Code Detection

`@code/dead` filters functions with `caller_count == 0`, excluding:
- CLI commands (`@click.command`, `@app.command`)
- Test functions (`test_*`, `*_test`)
- Dunder methods (`__init__`, `__str__`)
- AST visitors (`visit_*`, `generic_visit`)
- Exception classes (subclass of Exception)

## Output Schema

### @code/functions

```json
{
  "file": "src/jn/parser.py",
  "function": "parse_address",
  "type": "function",
  "class": null,
  "start_line": 49,
  "end_line": 129,
  "module": "src/jn",
  "caller_count": 9,
  "lines": 36,
  "hit": 35,
  "coverage": 97
}
```

### @code/calls

```json
{
  "caller": "parse_address",
  "callee": "_validate_address",
  "file": "src/jn/parser.py",
  "line": 127
}
```

## Usage Examples

```bash
# Low coverage functions
jn cat "@code/functions?root=src&lcov=coverage.lcov" \
  | jn filter 'select(.coverage < 50)' \
  | jn table

# Dead code
jn cat "@code/dead?root=src" | jn table

# Most called functions
jn cat "@code/functions?root=src" \
  | jn filter 'select(.caller_count > 0)' \
  | jq -sc 'sort_by(-.caller_count) | .[0:10] | .[]' \
  | jn table

# Call graph for specific file
jn cat "@code/calls?root=src&globs=**/parser.py" | jn table
```

## Demo

See `demos/code-lcov/` for a complete working example.

## Location

`jn_home/plugins/protocols/code_.py`
