# Tree-sitter Code Analysis Plugin

## Overview

The Tree-sitter plugin provides structural code analysis using the Tree-sitter parsing library. It enables:

1. **Code Analysis (Read Mode)** - Extract symbols, calls, imports, skeletons
2. **Surgical Refactoring (Write Mode)** - Replace function bodies with exact byte positions
3. **LCOV Integration** - Qualified function names for coverage data joins

## Architecture

### Why Tree-sitter?

- **Concrete Syntax Trees** - Preserves exact byte positions for surgical edits
- **Multi-language** - Python, JavaScript, TypeScript, Rust, Go, Java, C
- **Incremental Parsing** - Fast re-parsing for live editing
- **No External Dependencies** - Pure Python bindings via `tree-sitter-python`

### Plugin Design

```
┌─────────────────────────────────────────────────────────────┐
│                    treesitter_.py                           │
├─────────────────────────────────────────────────────────────┤
│  reads(config)                                              │
│    ├── --output-mode symbols  → extract_symbols()          │
│    ├── --output-mode calls    → extract_calls()            │
│    ├── --output-mode imports  → extract_imports()          │
│    ├── --output-mode skeleton → generate_skeleton()        │
│    ├── --output-mode strings  → extract_strings()          │
│    ├── --output-mode comments → extract_comments()         │
│    └── --output-mode decorators → extract_decorators()     │
├─────────────────────────────────────────────────────────────┤
│  writes(config)                                             │
│    └── --file path            → surgical code replacement   │
└─────────────────────────────────────────────────────────────┘
```

## Read Mode (Analysis)

### Output Modes

#### 1. Symbols Mode
Extract functions, classes, and methods with LCOV-compatible naming.

```bash
cat mycode.py | jn plugin call treesitter_ --mode read --output-mode symbols --filename mycode.py
```

Output:
```json
{"file": "mycode.py", "type": "method", "function": "Calculator.add", "name": "add", "start_line": 10, "end_line": 15, "lines": 6, "parent_class": "Calculator"}
{"file": "mycode.py", "type": "function", "function": "main", "name": "main", "start_line": 20, "end_line": 30, "lines": 11, "parent_class": null}
```

Key fields:
- `function`: Qualified name (Class.method) for LCOV join compatibility
- `name`: Simple function name
- `parent_class`: Containing class (null for top-level functions)

#### 2. Calls Mode
Extract function call graph.

```bash
cat mycode.py | jn plugin call treesitter_ --mode read --output-mode calls --filename mycode.py
```

Output:
```json
{"callee": "print", "caller": "main", "line": 25, "column": 4}
{"callee": "self.add", "caller": "calculate", "line": 12, "column": 8}
```

#### 3. Imports Mode
Extract import statements.

```bash
cat mycode.py | jn plugin call treesitter_ --mode read --output-mode imports --filename mycode.py
```

Output:
```json
{"module": "os", "names": null, "alias": null, "line": 1}
{"module": "pathlib", "names": ["Path"], "alias": null, "line": 2}
```

#### 4. Skeleton Mode
Generate code skeleton with function bodies replaced by `...` (for LLM context compression).

```bash
cat mycode.py | jn plugin call treesitter_ --mode read --output-mode skeleton --filename mycode.py
```

Output:
```json
{"file": "mycode.py", "content": "def add(a, b):\n    ...\n\ndef main():\n    ...", "functions_stripped": 2}
```

#### 5. Decorators Mode
Extract decorators and their targets (routes, fixtures, dataclasses).

```bash
cat app.py | jn plugin call treesitter_ --mode read --output-mode decorators --filename app.py
```

Output:
```json
{"decorator": "route", "args": "\"/users\"", "target": "get_users", "target_type": "function", "line": 10}
{"decorator": "dataclass", "args": null, "target": "User", "target_type": "class", "line": 5}
```

## Write Mode (Surgical Refactoring)

### Overview

Write mode enables precise code modifications using Tree-sitter's exact byte positions. This is the foundation for the "Dead Code Hunter" and other refactoring tools.

### Input Format

```json
{
  "target": "function:validate_email",
  "replace": "body",
  "code": "import re\nreturn bool(re.match(r'^[\\w.]+@[\\w.]+$', email))"
}
```

### Target Specification

| Format | Example | Description |
|--------|---------|-------------|
| `function:name` | `function:main` | Top-level function |
| `method:Class.name` | `method:Calculator.add` | Method in class |
| `class:name` | `class:Calculator` | Entire class |

### Replace Modes

| Mode | Description |
|------|-------------|
| `body` | Replace function body, preserve signature |
| `full` | Replace entire definition |

### Example: Body Replacement

```bash
echo '{"target": "function:validate_email", "replace": "body", "code": "return True"}' | \
  jn plugin call treesitter_ --mode write --file mycode.py
```

Output (dry-run by default):
```json
{
  "success": true,
  "target": "function:validate_email",
  "replace": "body",
  "modified": "... full modified source ..."
}
```

### Implementation Phases

#### Phase 1: Basic Body Replacement ✅ DONE

- Target specification parsing (function:name, method:class.name)
- Body vs full replacement modes
- Smart indentation detection from source context
- Re-indentation of replacement code to match target
- Dry-run output (returns modified code without writing)
- Syntax validation of resulting code

#### Phase 2: Multi-Edit Support ✅ DONE

- Multiple replacements in single pass
- Ordered by byte position (reverse order to preserve positions)
- Atomic operation (all succeed or all fail)
- Input format:
  ```json
  {"edits": [
    {"target": "function:foo", "replace": "body", "code": "return 1"},
    {"target": "function:bar", "replace": "body", "code": "return 2"}
  ]}
  ```

#### Phase 3: Insert/Delete Operations ✅ DONE

- Insert new function/method at position (after or before target)
- Delete function/class entirely
- Works in both single and batch modes
- Input formats:
  ```json
  {"operation": "insert", "after": "function:foo", "code": "def new_func(): pass"}
  {"operation": "insert", "before": "function:bar", "code": "def first(): pass"}
  {"operation": "delete", "target": "function:deprecated"}
  ```

#### Phase 4: Advanced Targets 📋 PLANNED

- Line range targeting: `lines:10-20`
- Node type targeting: `decorator:route`
- Pattern matching: `method:*.test_*`
- Import manipulation: `import:os`

#### Phase 5: Write-Back Support 📋 PLANNED

- Actual file modification (with `--write` flag)
- Backup creation before modification
- Pre/post validation hooks
- Git-aware mode (refuse if uncommitted changes)

## LCOV Join Integration

Tree-sitter symbols use qualified function names to match LCOV coverage format:

```bash
# Extract symbols
cat mycode.py | jn plugin call treesitter_ --mode read --output-mode symbols --filename mycode.py > symbols.json

# Join with coverage
jn cat coverage.lcov | jn join symbols.json --left-key function --right-key function --target code_info
```

Result: Coverage data enriched with code structure (line counts, class context).

## Use Cases

### 1. Dead Code Hunter
Find untested functions with code context:

```bash
jn cat coverage.lcov | \
  jn join symbols.json --left-key function --right-key function --target code | \
  jn filter 'select(.hit_count == 0)' | \
  jn filter '{function, lines: .code[0].lines, file: .code[0].file}'
```

### 2. LLM Context Compression
Generate skeleton for large codebase:

```bash
cat huge_module.py | \
  jn plugin call treesitter_ --mode read --output-mode skeleton --filename huge_module.py | \
  jn filter '.content'
```

### 3. API Route Discovery
Find all Flask/FastAPI routes:

```bash
cat app.py | \
  jn plugin call treesitter_ --mode read --output-mode decorators --filename app.py | \
  jn filter 'select(.decorator | test("route|get|post|put|delete"))'
```

### 4. Surgical Test Stub Generation
Replace function bodies with test stubs:

```bash
echo '{"target": "function:complex_calculation", "replace": "body", "code": "return 42  # TODO: implement"}' | \
  jn plugin call treesitter_ --mode write --file mycode.py
```

## Supported Languages

| Language | Extension | Status |
|----------|-----------|--------|
| Python | .py | ✅ Full support |
| JavaScript | .js | ✅ Full support |
| TypeScript | .ts, .tsx | ✅ Full support |
| JSX | .jsx | ✅ Full support |
| Rust | .rs | ✅ Symbols/calls |
| Go | .go | ✅ Symbols/calls |
| Java | .java | ✅ Symbols/calls |
| C | .c, .h | ✅ Symbols/calls |

## Configuration

### CLI Options

| Option | Description |
|--------|-------------|
| `--mode read\|write` | Operation mode |
| `--output-mode` | Read mode output type |
| `--filename` | Source filename (for language detection) |
| `--file` | File path for write operations |

### Environment

- `TREE_SITTER_DIR`: Custom grammar directory (optional)

## Demo

See `demos/treesitter-analysis/` for complete examples:

```bash
cd demos/treesitter-analysis
./run_demo.sh
```

Demonstrates:
- All read modes (symbols, calls, imports, skeleton, decorators)
- Write mode (body replacement, method replacement, full replacement)
- LCOV join for dead code detection
