# Tree-sitter + LCOV: Language-Agnostic Coverage Analysis

## Goal

Enable language-agnostic function-level coverage analysis that:
- Works with **any** LCOV file (C, Go, Rust, Python, JS, etc.)
- Produces **better** output than coverage.py's HTML report
- Uses **natural joins** - schemas align, commands are simple

## The Design

### Schema Alignment

**Tree-sitter output** (functions with line ranges):
```json
{"file": "src/cli/vd.py", "function": "vd", "start_line": 27, "end_line": 249}
```

**LCOV output** (lines with execution data):
```json
{"file": "src/cli/vd.py", "line": 66, "executed": false}
```

Common field: `file`. Range condition: `line ∈ [start_line, end_line]`.

### The Pipeline

```bash
# Extract functions → Join with coverage → Aggregate → Display
jn cat "src/**/*.py" --plugin ts_ \
  | jn join coverage.lcov~lcov?mode=lines \
      --on file \
      --where ".line >= .start_line and .line <= .end_line" \
      --agg "total: count, hit: sum(.executed)" \
  | jn filter '.coverage = (.hit / .total * 100 | floor)' \
  | jn table --sort coverage
```

### Output (Better than htmlcov)

```
file                          function                   total   hit  coverage
──────────────────────────────────────────────────────────────────────────────
src/jn/profiles/gmail.py      load_gmail_profile            12     0        0%
src/jn/profiles/gmail.py      resolve_gmail_reference       12     0        0%
src/jn/cli/commands/vd.py     vd                            90     0        0%
src/jn/shell/jc_fallback.py   execute_with_jc               68     0        0%
src/jn/cli/commands/sh.py     sh                            36     0        0%
...
```

## Components

### 1. Tree-sitter Plugin (`ts_.py`)

Extracts functions/methods/classes from source files.

```bash
jn cat file.py --plugin ts_
jn cat "src/**/*.py" --plugin ts_    # glob support
```

**Output schema:**
```json
{
  "file": "src/jn/filtering.py",
  "function": "parse_operator",
  "type": "function",
  "class": null,
  "start_line": 7,
  "end_line": 49
}
```

**Supported languages:** Python, JavaScript, TypeScript, Go, Rust, C, C++, Java

### 2. Enhanced `jn join`

Add three new options:

| Option | Purpose | Example |
|--------|---------|---------|
| `--on FIELD` | Join on common field (natural join) | `--on file` |
| `--where EXPR` | Filter matches with jq expression | `--where ".line >= .start_line"` |
| `--agg SPEC` | Aggregate matches inline | `--agg "total: count, hit: sum(.executed)"` |

**Without aggregation** (embed matches):
```bash
jn join right.json --on file --where ".x > .y" --target matches
# Output: {"file": "a.py", "matches": [{...}, {...}]}
```

**With aggregation** (compute stats):
```bash
jn join right.json --on file --where ".x > .y" --agg "n: count, total: sum(.value)"
# Output: {"file": "a.py", "n": 5, "total": 100}
```

### 3. LCOV Plugin (already exists)

```bash
jn cat coverage.lcov --mode=lines
```

## Implementation

### Phase 1: ts_ plugin

```python
#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["tree-sitter>=0.24", "tree-sitter-python>=0.24", ...]
# [tool.jn]
# matches = []  # explicit --plugin only
# ///

def reads(config):
    """Extract functions from source file."""
    lang = detect_language(config.get('file'))
    parser = get_parser(lang)
    tree = parser.parse(source_bytes)

    for func in extract_functions(tree, lang):
        yield {
            'file': config['file'],
            'function': func.qualified_name,
            'type': func.type,  # function, method, class
            'class': func.class_name,
            'start_line': func.start_line,
            'end_line': func.end_line,
        }
```

### Phase 2: Enhanced join

```python
# In src/jn/cli/commands/join.py

@click.option('--on', 'join_field', help='Field to join on (natural join)')
@click.option('--where', 'where_expr', help='jq expression to filter matches')
@click.option('--agg', 'agg_spec', help='Aggregation: "name: func, ..."')

def _stream_and_enrich(..., join_field, where_expr, agg_spec):
    for left_record in stdin:
        key = left_record.get(join_field)
        matches = lookup.get(str(key), [])

        # Apply where filter
        if where_expr:
            matches = [m for m in matches if eval_jq(where_expr, {**left_record, **m})]

        # Aggregate or embed
        if agg_spec:
            left_record.update(aggregate(matches, agg_spec))
        else:
            left_record[target] = matches

        yield left_record
```

## Demo Script

```bash
#!/bin/bash
# demo/coverage.sh - Analyze jn's own coverage

# Ensure coverage data exists
[ -f coverage.lcov ] || make coverage

echo "=== Function Coverage Report ==="
echo ""

jn cat "src/jn/**/*.py" --plugin ts_ \
  | jn join coverage.lcov~lcov?mode=lines \
      --on file \
      --where ".line >= .start_line and .line <= .end_line" \
      --agg "total: count, hit: sum(.executed)" \
  | jn filter '.coverage = (if .total > 0 then (.hit / .total * 100 | floor) else 0 end)' \
  | jn filter 'sort_by(.coverage)' \
  | jn table --columns file,function,total,hit,coverage

echo ""
echo "=== Summary ==="
jn cat "src/jn/**/*.py" --plugin ts_ \
  | jn join coverage.lcov~lcov?mode=lines \
      --on file \
      --where ".line >= .start_line and .line <= .end_line" \
      --agg "total: count, hit: sum(.executed)" \
  | jn filter '{
      functions: length,
      zero_coverage: [.[] | select(.hit == 0)] | length,
      full_coverage: [.[] | select(.hit == .total)] | length
    }'
```

## Success Criteria

1. **Simple:** Demo is <15 lines of shell
2. **Accurate:** Matches coverage.py HTML report numbers
3. **Universal:** Works with any LCOV file, any tree-sitter language
4. **Fast:** Processes jn codebase in <3 seconds

## File Locations

- Plugin: `jn_home/plugins/formats/ts_.py`
- Join enhancements: `src/jn/cli/commands/join.py`
- Demo: `demo/coverage.sh`
