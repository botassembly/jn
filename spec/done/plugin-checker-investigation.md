# Plugin Checker AST Investigation & 20 Recommended Checks

**Date:** 2025-11-11
**Status:** Investigation Complete
**Related:** spec/design/plugin-checker.md

## Executive Summary

This document presents findings from investigating AST-based static analysis techniques and analyzing the JN codebase to identify 20 specific checks that should be implemented in the plugin checker tool.

**Key Findings:**
- AST checking via `ast.parse()` + `ast.NodeVisitor` is straightforward and performant
- 20 checks identified across 4 categories (Critical Backpressure, Architecture, Error Handling, Code Quality)
- 6 checks should block PRs immediately (Phase 1)
- Current plugins mostly follow good patterns (jq_.py is exemplary)
- Some legitimate exceptions needed (json_.py, csv_.py buffer by necessity)

---

## 1. AST Implementation Approach

### How AST Checking Works

**Core technique:**
```python
import ast

class SubprocessChecker(ast.NodeVisitor):
    def __init__(self):
        self.violations = []

    def visit_Call(self, node):
        # Detect subprocess.run with capture_output
        if (isinstance(node.func, ast.Attribute) and
            node.func.attr == 'run' and
            isinstance(node.func.value, ast.Name) and
            node.func.value.id == 'subprocess'):

            # Check keywords for capture_output=True
            for kw in node.keywords:
                if kw.arg == 'capture_output':
                    if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        self.violations.append({
                            'rule': 'capture_output',
                            'line': node.lineno,
                            'col': node.col_offset,
                            'message': 'subprocess.run with capture_output=True'
                        })

        self.generic_visit(node)

# Usage
with open('plugin.py') as f:
    tree = ast.parse(f.read())
    checker = SubprocessChecker()
    checker.visit(tree)
    print(checker.violations)
```

**Key AST Node Types:**
- `ast.Call` - Function/method calls (subprocess.run, print, etc.)
- `ast.Import`, `ast.ImportFrom` - Import statements
- `ast.Assign` - Variable assignments (track Popen processes)
- `ast.Attribute` - Attribute access (process.stdout.close())
- `ast.Try` - Try-except blocks
- `ast.FunctionDef` - Function definitions
- `ast.Module` - Module-level (check for docstring)

**State tracking example:**
```python
class PopenTracker(ast.NodeVisitor):
    def __init__(self):
        self.popen_vars = {}  # name -> {has_stdout_pipe, closed, waited}

    def visit_Assign(self, node):
        # Track: fetch = subprocess.Popen(..., stdout=PIPE)
        if self._is_popen_call(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.popen_vars[target.id] = {
                        'line': node.lineno,
                        'has_stdout_pipe': self._has_stdout_pipe(node.value),
                        'closed': False,
                        'waited': False
                    }

    def visit_Call(self, node):
        # Track: fetch.stdout.close()
        if (isinstance(node.func, ast.Attribute) and
            node.func.attr == 'close'):
            if isinstance(node.func.value, ast.Attribute):
                if node.func.value.attr == 'stdout':
                    var_name = node.func.value.value.id
                    if var_name in self.popen_vars:
                        self.popen_vars[var_name]['closed'] = True
```

### Performance Characteristics

- **Speed:** Parsing + traversal <10ms for typical plugin (~200 lines)
- **Memory:** ~1MB for AST tree of typical plugin
- **False positives:** Minimize with careful pattern matching
- **False negatives:** Accept some (better than overwhelming with noise)

---

## 2. Comprehensive List of 20 Checks

### Category A: Critical Backpressure Violations ⚠️

#### 1. subprocess.run with capture_output=True
**Why:** Buffers entire output in memory, defeats streaming
**Severity:** ERROR
**AST Pattern:**
```python
def visit_Call(self, node):
    if (node.func.attr == 'run' and
        node.func.value.id == 'subprocess'):
        for kw in node.keywords:
            if kw.arg == 'capture_output' and kw.value.value is True:
                self.report(node.lineno, "subprocess.run with capture_output=True")
```
**Reference:** spec/arch/backpressure.md:18-29

#### 2. Missing stdout.close() after Popen chaining
**Why:** Breaks SIGPIPE propagation, prevents early termination
**Severity:** ERROR
**AST Pattern:** Track Popen assignments with stdout=PIPE, verify .close() called when stdout passed to another process
**Reference:** spec/arch/backpressure.md:107-156

#### 3. Reading all data before processing (.read() with no args)
**Why:** Loads entire dataset into memory, defeats streaming
**Severity:** ERROR
**AST Pattern:**
```python
def visit_Call(self, node):
    # Detect: all_data = process.stdout.read()  # No size argument
    if (isinstance(node.func, ast.Attribute) and
        node.func.attr == 'read' and
        len(node.args) == 0):  # No size limit
        # Check if it's on a stdout/stdin stream
        self.report(node.lineno, "Reading all data before processing")
```
**Reference:** spec/arch/backpressure.md:357-373
**Whitelist:** json_.py (JSON format requires full parse)

#### 4. Missing wait() calls for spawned processes
**Why:** Zombie processes, unchecked exit codes, resource leaks
**Severity:** ERROR
**AST Pattern:** Track Popen assignments, verify .wait() called before function exit
**Reference:** spec/arch/backpressure.md:375-392

#### 5. Using threading.Thread instead of subprocess for pipelines
**Why:** No parallelism (GIL), no automatic backpressure, shared memory bugs
**Severity:** ERROR
**AST Pattern:**
```python
def visit_Import(self, node):
    for alias in node.names:
        if alias.name == 'threading':
            self.has_threading_import = True

def visit_Call(self, node):
    if (self.has_threading_import and
        isinstance(node.func, ast.Attribute) and
        node.func.attr == 'Thread'):
        self.report(node.lineno, "Using threads instead of processes")
```
**Reference:** spec/arch/backpressure.md:395-448

---

### Category B: Plugin Architecture Violations 🏗️

#### 6. Missing PEP 723 script block
**Why:** UV won't manage dependencies, plugin won't work in isolation
**Severity:** ERROR
**Detection:** Regex (not AST), check for `# /// script` block
```python
PEP723_PATTERN = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\n(?P<content>(^#(| .*)$\n)+)^# ///$"
)
match = PEP723_PATTERN.search(file_contents)
if not match or match.group("type") != "script":
    report("Missing PEP 723 script block")
```

#### 7. Missing PEP 723 dependencies for imports
**Why:** Runtime import errors in isolated UV environments
**Severity:** ERROR
**AST Pattern:**
```python
# Extract all imports from AST
imports = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports.add(alias.name.split('.')[0])
    elif isinstance(node, ast.ImportFrom):
        imports.add(node.module.split('.')[0])

# Parse PEP 723 dependencies
declared = set(dep.split('>=')[0].split('==')[0] for dep in pep723_deps)

# Check for undeclared imports (exclude stdlib)
missing = imports - declared - STDLIB_MODULES
if missing:
    report(f"Missing dependencies: {missing}")
```
**Reference:** spec/design/plugin-checker.md:206-238

#### 8. Missing UV shebang
**Why:** Plugin won't be executable directly, UV won't manage environment
**Severity:** ERROR
**Detection:** Check first line
```python
if not file_contents.startswith('#!/usr/bin/env -S uv run --script'):
    report("Missing UV shebang")
```

#### 9. Missing [tool.jn] metadata section
**Why:** Plugin won't be discovered, no pattern matching
**Severity:** WARNING (filters like jq_ don't need matches)
**Detection:** Parse PEP 723, check for `[tool.jn]` section

#### 10. Plugin missing reads() or writes() function
**Why:** Format plugins need at least one for duck typing
**Severity:** WARNING (protocols like http_ may use different pattern)
**AST Pattern:**
```python
def visit_FunctionDef(self, node):
    if node.name in ('reads', 'writes'):
        self.has_plugin_function = True
```

#### 11. Missing flush=True in plugin print() calls
**Why:** Buffering defeats streaming, causes pipeline stalls
**Severity:** ERROR
**AST Pattern:**
```python
def visit_Call(self, node):
    if (isinstance(node.func, ast.Name) and node.func.id == 'print'):
        # Check if json.dumps is in args (NDJSON output)
        has_json_dumps = any(
            isinstance(arg, ast.Call) and
            getattr(arg.func, 'attr', None) == 'dumps'
            for arg in node.args
        )
        if has_json_dumps:
            # Check for flush=True keyword
            has_flush = any(
                kw.arg == 'flush' and
                isinstance(kw.value, ast.Constant) and
                kw.value.value is True
                for kw in node.keywords
            )
            if not has_flush:
                self.report(node.lineno, "Missing flush=True in print()")
```
**Pattern:** All plugins use `print(json.dumps(record), flush=True)`

---

### Category C: Error Handling Patterns 🚨

#### 12. Overly broad try-catch blocks
**Why:** Catches unintended exceptions, masks bugs
**Severity:** WARNING
**AST Pattern:**
```python
def visit_Try(self, node):
    # Count lines in try body
    try_start = node.lineno
    try_end = node.body[-1].lineno if node.body else try_start
    try_lines = try_end - try_start + 1

    # Check exception specificity
    for handler in node.handlers:
        if handler.type:  # Specific exception
            if try_lines > 10:  # Threshold
                self.report(try_start,
                    f"Try-catch too broad: {try_lines} lines")
```
**Reference:** spec/design/plugin-checker.md:240-273

#### 13. Bare except: clause
**Why:** Catches KeyboardInterrupt, SystemExit, masks all errors
**Severity:** ERROR
**AST Pattern:**
```python
def visit_ExceptHandler(self, node):
    if node.type is None:  # Bare except:
        self.report(node.lineno, "Bare except clause")
```

#### 14. Raising exceptions in plugin data flow
**Why:** Breaks pipelines, doesn't follow error-as-data pattern
**Severity:** WARNING
**AST Pattern:**
```python
def visit_FunctionDef(self, node):
    if node.name in ('reads', 'writes'):
        # Track raises inside these functions
        for child in ast.walk(node):
            if isinstance(child, ast.Raise):
                # Allow at top level (validation)
                # Warn if inside loops (data flow)
                if self._is_inside_loop(child, node):
                    self.report(child.lineno,
                        "Raising exception in data flow (use error_record instead)")
```
**Pattern:** Plugins should `yield {"_error": True, ...}`, not raise in loops

#### 15. Missing custom exception base class in core
**Why:** Framework code should have specific exception types
**Severity:** WARNING (core code only)
**Pattern:** Core should define PipelineError, ProfileError, etc.
```python
# Check if file is in src/jn/core/
if 'src/jn/core/' in filepath or 'src/jn/profiles/' in filepath:
    # Verify custom exceptions exist
    has_custom_exception = any(
        isinstance(node, ast.ClassDef) and
        any(isinstance(base, ast.Name) and base.id == 'Exception'
            for base in node.bases)
        for node in ast.walk(tree)
    )
```

---

### Category D: Code Quality & Style 📝

#### 16. Config dict pattern in plugin functions
**Why:** Less type-safe than discrete parameters, harder to validate
**Severity:** WARNING (low priority)
**AST Pattern:**
```python
def visit_FunctionDef(self, node):
    if node.name in ('reads', 'writes'):
        for arg in node.args.args:
            if arg.arg == 'config':
                # Check type annotation
                if (arg.annotation and
                    isinstance(arg.annotation, ast.Subscript) and
                    getattr(arg.annotation.value, 'id', None) == 'Optional'):
                    self.report(node.lineno, "Config dict pattern (consider discrete params)")
```
**Reference:** spec/design/plugin-checker.md:306-334
**Note:** Legacy pattern, new plugins should use direct args (like http_.py)

#### 17. Missing module docstring
**Why:** Poor documentation, unclear purpose
**Severity:** WARNING
**AST Pattern:**
```python
if (not tree.body or
    not isinstance(tree.body[0], ast.Expr) or
    not isinstance(tree.body[0].value, ast.Constant) or
    not isinstance(tree.body[0].value.value, str)):
    report("Missing module docstring")
```

#### 18. Missing function docstrings for reads/writes
**Why:** No documentation of plugin behavior
**Severity:** WARNING
**AST Pattern:**
```python
def visit_FunctionDef(self, node):
    if node.name in ('reads', 'writes'):
        if (not node.body or
            not isinstance(node.body[0], ast.Expr) or
            not isinstance(node.body[0].value, ast.Constant)):
            self.report(node.lineno, f"Missing docstring for {node.name}()")
```

#### 19. Inconsistent import organization
**Why:** Hard to read, PEP 8 violations
**Severity:** WARNING (low priority)
**Check:** stdlib imports, then third-party, then local (separated by blank lines)
**AST Pattern:** Track import nodes, verify grouping order

#### 20. Using sys.stdin.read() in plugins (anti-pattern)
**Why:** Buffers all data, defeats streaming
**Severity:** ERROR (with exceptions)
**AST Pattern:**
```python
def visit_Call(self, node):
    if (isinstance(node.func, ast.Attribute) and
        node.func.attr == 'read' and
        isinstance(node.func.value, ast.Attribute) and
        node.func.value.attr == 'stdin'):
        self.report(node.lineno, "Reading all stdin (consider streaming)")
```
**Whitelist:** json_.py, formats that require full parse

---

## 3. Priority & Implementation Order

### Phase 1: Critical (Block PRs) 🚫
Implement first, enforce immediately, exit code 1

1. **subprocess.run with capture_output** (#1)
2. **Missing stdout.close()** (#2)
3. **Missing wait() calls** (#4)
4. **Missing PEP 723 dependencies** (#7)
5. **Missing flush=True** (#11)
6. **Bare except clauses** (#13)

**Rationale:** These cause bugs, memory issues, or runtime failures

### Phase 2: Important (Warn in PRs) ⚠️
Implement second, warn but don't block, exit code 0

1. **Reading all data (.read())** (#3)
2. **Using threading** (#5)
3. **Missing PEP 723 block** (#6)
4. **Missing UV shebang** (#8)
5. **Overly broad try-catch** (#12)
6. **Raising exceptions in data flow** (#14)

**Rationale:** Architectural issues, should fix but not immediate blockers

### Phase 3: Code Quality (Optional) 📋
Implement last, informational only, always exit 0

1. **Plugin structure warnings** (#9-10)
2. **Documentation** (#17-18)
3. **Code style** (#15-16, #19)
4. **Streaming patterns** (#20)

**Rationale:** Nice to have, helps maintain consistency

---

## 4. Special Cases & Exceptions

### Whitelist Patterns

**Legitimate buffering:**
```python
# .jncheck.toml
[rules.streaming]
allow_read_all = [
    "json_",      # JSON arrays require full parse
    "csv_",       # CSV writer needs all columns for header
    "yaml_"       # YAML documents are parsed as whole
]
```

**Core exception handling:**
```python
[rules.exceptions]
allow_raises_in = [
    "src/jn/core/*",      # Core can raise PipelineError
    "src/jn/profiles/*"   # Profiles can raise ProfileError
]
```

**Plugin patterns:**
```python
[rules.plugin_structure]
require_reads_writes = false  # Some plugins (http_) use different pattern
require_matches = false        # Filters (jq_) don't need matches
```

### Test File Exclusions

All checks should exclude:
- `tests/**/*.py` - Test files
- `archive/**/*.py` - Archived code
- `**/__pycache__/**` - Compiled bytecode
- `**/test_*.py` - Test files by name pattern

---

## 5. Output Format Recommendations

### Text Format (Human-Readable)

```
$ jn check plugins

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Checking: csv_ (jn_home/plugins/formats/csv_.py)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ PASS: No subprocess.run with capture_output
✅ PASS: No missing stdout.close()
✅ PASS: No missing wait() calls
✅ PASS: All imports have PEP 723 dependencies
⚠️  WARN: Config dict pattern found

   Line 19: def reads(config: Optional[dict] = None):
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   Suggestion: Consider using discrete function parameters
   Example:
     def reads(delimiter: str = ',', skip_rows: int = 0):

   Why: More type-safe, easier validation, better IDE support

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Checking: jq_ (jn_home/plugins/filters/jq_.py)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ All checks passed! 🎉

   Exemplary implementation:
   • Uses Popen (not run) for streaming
   • Inherits stdin/stdout for zero buffering
   • Properly waits for subprocess
   • Minimal, focused, follows Unix philosophy

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Checking: bad_example (custom/bad_example.py)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ ERROR: subprocess.run with capture_output=True

   bad_example.py:45
   45│ result = subprocess.run(['curl', url], capture_output=True)
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   Problem: Buffers entire output in memory
   Impact: 1GB file → 2GB RAM usage, no streaming

   Fix:
     # Replace with:
     proc = subprocess.Popen(['curl', url], stdout=subprocess.PIPE)
     for line in proc.stdout:
         process(line)
     proc.wait()

   Reference: spec/arch/backpressure.md:18-29

❌ ERROR: Missing flush=True in print()

   bad_example.py:52
   52│ print(json.dumps(record))
       ^^^^^^^^^^^^^^^^^^^^^^^^^

   Problem: Buffering defeats streaming
   Impact: Pipeline stalls, backpressure doesn't work

   Fix:
     print(json.dumps(record), flush=True)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Checked: 3 plugins
  ✅ 2 passed
  ❌ 1 failed

Issues found: 2 errors, 1 warning

Exit code: 1 (errors present)
```

### JSON Format (CI/CD)

```json
{
  "summary": {
    "checked": 3,
    "passed": 2,
    "failed": 1,
    "errors": 2,
    "warnings": 1
  },
  "results": [
    {
      "plugin": "csv_",
      "path": "jn_home/plugins/formats/csv_.py",
      "violations": [
        {
          "rule": "config_dict_pattern",
          "severity": "warning",
          "line": 19,
          "column": 4,
          "message": "Config dict pattern found",
          "suggestion": "Use discrete function parameters"
        }
      ]
    },
    {
      "plugin": "bad_example",
      "path": "custom/bad_example.py",
      "violations": [
        {
          "rule": "subprocess_capture_output",
          "severity": "error",
          "line": 45,
          "column": 9,
          "message": "subprocess.run with capture_output=True",
          "reference": "spec/arch/backpressure.md:18-29"
        },
        {
          "rule": "missing_flush",
          "severity": "error",
          "line": 52,
          "column": 4,
          "message": "Missing flush=True in print()"
        }
      ]
    }
  ]
}
```

---

## 6. Codebase Analysis Findings

### Patterns That Work Well ✅

**Gold standard: jq_.py**
```python
# Minimal, correct, exemplary
proc = subprocess.Popen(['jq', '-c', query],
                       stdin=sys.stdin,
                       stdout=sys.stdout,
                       stderr=sys.stderr)
sys.exit(proc.wait())
```
- Uses Popen (not run)
- Inherits stdin/stdout (zero buffering)
- Properly waits and propagates exit code
- Minimal implementation (~35 lines)

**Good pattern: http_.py direct args**
```python
def reads(url: str, method: str = 'GET', headers: dict = None, ...):
    # Direct parameters, not config dict
    # Type hints for validation
    # Clear signature
```

**Error records pattern**
```python
def error_record(error_type: str, message: str, **extra) -> dict:
    return {"_error": True, "type": error_type, "message": message, **extra}

# Usage in plugin:
yield error_record("http_error", f"HTTP {status_code}", url=url)
```
- Errors as data (not exceptions)
- Pipelines continue processing
- Downstream can filter/handle errors

**Exception hierarchy**
```python
class PipelineError(Exception): pass
class ProfileError(Exception): pass
```
- Specific exceptions for framework
- Clear error domains
- Easy to catch selectively

### Current Anti-Patterns Found 📋

**Legacy config dict pattern:**
```python
# Found in: csv_.py, json_.py, yaml_.py
def reads(config: Optional[dict] = None):
    config = config or {}
    delimiter = config.get('delimiter', ',')
    # ... many .get() calls
```
**Why problematic:** No type checking, hard to validate, unclear signature
**Migration path:** Add warnings, update docs, new plugins use direct args

**Necessary buffering (not fixable):**
```python
# json_.py - JSON arrays require full parse
content = sys.stdin.read()
data = json.loads(content)

# csv_.py writes() - Need all column names
records = []
for line in sys.stdin:
    records.append(json.loads(line))
# Then write with all columns
```
**Why acceptable:** Format limitations, document as exceptions

### Recommendations for Implementation

1. **Start with Phase 1 checks** - Most impactful, block real bugs
2. **Add configuration support early** - Whitelist patterns (.jncheck.toml)
3. **Make error messages actionable** - Show fix, not just problem
4. **Include references** - Link to spec docs for learning
5. **Test against all bundled plugins** - Ensure no false positives
6. **Add auto-fix mode later** - `jn check --fix` for simple issues
7. **CI/CD integration** - GitHub Actions with `jn check all`

---

## 7. Next Steps

### Implementation Path

**Week 1: Core Infrastructure**
- [ ] Create `src/jn/checker/` directory structure
- [ ] Implement `ast_checker.py` base class (NodeVisitor framework)
- [ ] Implement `scanner.py` (find files to check)
- [ ] Implement `report.py` (format violations)
- [ ] Create `jn check` CLI command (basic)

**Week 2: Phase 1 Rules (Critical)**
- [ ] Rule #1: subprocess.run with capture_output
- [ ] Rule #2: Missing stdout.close()
- [ ] Rule #4: Missing wait()
- [ ] Rule #7: Missing PEP 723 dependencies
- [ ] Rule #11: Missing flush=True
- [ ] Rule #13: Bare except clauses
- [ ] Write tests for each rule
- [ ] Test against bundled plugins

**Week 3: Phase 2 Rules (Important)**
- [ ] Rule #3: Reading all data
- [ ] Rule #5: Using threading
- [ ] Rule #6: Missing PEP 723 block
- [ ] Rule #8: Missing UV shebang
- [ ] Rule #12: Overly broad try-catch
- [ ] Rule #14: Raising in data flow
- [ ] Configuration support (.jncheck.toml)

**Week 4: Polish & Integration**
- [ ] Phase 3 rules (code quality)
- [ ] Output formatting (text + JSON)
- [ ] CI/CD integration
- [ ] Documentation
- [ ] Pre-commit hook example

### Testing Strategy

```python
# tests/checker/test_subprocess_rules.py
def test_detect_capture_output():
    code = '''
result = subprocess.run(cmd, capture_output=True)
    '''
    violations = check_code(code, rules=['subprocess'])
    assert len(violations) == 1
    assert violations[0]['rule'] == 'capture_output'

def test_detect_missing_stdout_close():
    code = '''
fetch = subprocess.Popen(['curl', url], stdout=subprocess.PIPE)
parse = subprocess.Popen(['parser'], stdin=fetch.stdout)
# Missing: fetch.stdout.close()
    '''
    violations = check_code(code, rules=['backpressure'])
    assert any(v['rule'] == 'missing_stdout_close' for v in violations)
```

---

## 8. Conclusion

AST-based checking is:
- ✅ **Feasible** - Python's ast module is straightforward
- ✅ **Fast** - <10ms per plugin
- ✅ **Effective** - Can catch all 20 identified patterns
- ✅ **Extensible** - Easy to add new rules
- ✅ **Educational** - Error messages teach principles

The 20 checks span:
- **Critical backpressure violations** (prevent bugs)
- **Architecture patterns** (enforce design)
- **Error handling** (improve robustness)
- **Code quality** (maintain consistency)

**Recommended action:** Implement Phase 1 rules first (6 critical checks), then iterate based on feedback.
