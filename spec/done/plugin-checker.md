# Plugin Code Checker - AST-Based Anti-Pattern Detection

## Overview

An AST-based static analysis tool that detects architectural violations in JN core code and plugins. Enforces the streaming/backpressure principles and catches common mistakes before they break production.

## The Problem

**JN's architecture relies on critical patterns:**
- Popen (not run) for streaming
- stdout.close() for SIGPIPE propagation
- Incremental processing (not buffering)
- PEP 723 dependency declarations

**Without automated checking:**
- Contributors might use subprocess.run(capture_output=True)
- Missing stdout.close() breaks early termination
- Buffering defeats constant memory guarantees
- Missing dependencies cause runtime failures

**We need:** Automated detection before code review or runtime.

## Goals

### Functional
1. Detect anti-patterns in plugin code
2. Detect anti-patterns in core JN code
3. Runnable via `jn plugin check` CLI
4. Runnable in CI/CD pipeline
5. Clear, actionable error messages with line numbers

### Non-Functional
1. Fast (<1s for typical plugin)
2. Zero false positives (high precision)
3. Extensible (easy to add new rules)
4. No plugin execution required (pure static analysis)

## Architecture

### Components

```
jn check [target]
       ↓
src/jn/cli/commands/check.py
       ↓
src/jn/checker/
  ├── __init__.py
  ├── ast_checker.py        # AST traversal engine
  ├── scanner.py            # Find files to check (core, plugins, specific)
  ├── rules/
  │   ├── __init__.py
  │   ├── subprocess_rules.py    # Popen/run/capture_output
  │   ├── backpressure_rules.py  # stdout.close(), buffering
  │   ├── dependency_rules.py    # PEP 723 validation
  │   └── exception_rules.py     # Try-catch scope
  └── report.py             # Error formatting
```

### Execution Flow

```
1. Parse target: core | plugins | all | [plugin_name]
2. Discovery:
   - core: Find all .py files in src/jn/
   - plugins: Find all .py in jn_home/plugins/, ~/.local/jn/plugins/, $JN_HOME/plugins/
   - all: core + plugins
   - [plugin_name]: Search for specific plugin file
3. Parse: ast.parse(file_contents) → AST tree (per file)
4. Analyze: Walk AST, apply rules (per file)
5. Report: Format violations with line numbers
6. Exit: 0 if all clean, 1 if any violations
```

## Detection Rules

### Rule 1: subprocess.run with capture_output

**Anti-pattern:**
```python
result = subprocess.run(cmd, capture_output=True)
data = result.stdout  # Buffers entire output!
```

**AST Detection:**
- Find `ast.Call` nodes where `func.attr == 'run'` and `func.value.id == 'subprocess'`
- Check if any keyword arg has `arg == 'capture_output'` and `value == True`

**Error message:**
```
backpressure.md line 18: subprocess.run with capture_output=True
  plugin.py:42: result = subprocess.run(cmd, capture_output=True)
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  ❌ Anti-pattern: Buffers entire output in memory
  ✅ Fix: Use subprocess.Popen with pipes for streaming

  See: spec/arch/backpressure.md (The Problem: Memory Buffering)
```

### Rule 2: Missing stdout.close() After Popen

**Anti-pattern:**
```python
fetch = subprocess.Popen(cmd1, stdout=subprocess.PIPE)
parse = subprocess.Popen(cmd2, stdin=fetch.stdout, stdout=subprocess.PIPE)
# Missing: fetch.stdout.close()
```

**AST Detection:**
- Track subprocess.Popen assignments that create stdout=PIPE
- Check if that variable's stdout attribute is passed as stdin to another Popen
- Verify `.close()` is called on that stdout within same scope

**Error message:**
```
backpressure.md line 117: Missing stdout.close() for SIGPIPE propagation
  plugin.py:45: parse = subprocess.Popen(..., stdin=fetch.stdout, ...)
  plugin.py:47: for line in parse.stdout:
                ^^^^^^^^^^^^^^^^^^^^^^^
  ❌ Missing: fetch.stdout.close() between lines 45-47
  ✅ Fix: Add fetch.stdout.close() after creating parse process

  Why: Without close(), SIGPIPE won't propagate if downstream exits early
  See: spec/arch/backpressure.md (Critical Implementation Detail)
```

### Rule 3: Reading All Data Before Processing

**Anti-pattern:**
```python
all_data = process.stdout.read()  # Buffers everything
for line in all_data.split('\n'):
    process_line(line)
```

**AST Detection:**
- Find `process.stdout.read()` calls (no arguments = read all)
- Flag if not part of streaming iteration pattern

**Error message:**
```
backpressure.md line 360: Reading all data before processing
  plugin.py:52: all_data = process.stdout.read()
                           ^^^^^^^^^^^^^^^^^^^^^
  ❌ Anti-pattern: Buffers entire output before processing
  ✅ Fix: Stream line-by-line: for line in process.stdout

  See: spec/arch/backpressure.md (Mistake 3)
```

### Rule 4: Missing wait() After Popen

**Anti-pattern:**
```python
fetch = subprocess.Popen(cmd, stdout=subprocess.PIPE)
parse = subprocess.Popen(cmd2, stdin=fetch.stdout, stdout=subprocess.PIPE)
# Output consumed but no wait() calls
for line in parse.stdout:
    print(line)
# Missing: parse.wait(), fetch.wait()
```

**AST Detection:**
- Track Popen assignments
- Check if `.wait()` is called on those variables before function exit

**Error message:**
```
backpressure.md line 378: Missing wait() calls for spawned processes
  plugin.py:45: fetch = subprocess.Popen(...)
  plugin.py:46: parse = subprocess.Popen(...)
  ...
  plugin.py:60: # End of function
  ❌ No wait() calls found for: fetch, parse
  ✅ Fix: Add fetch.wait() and parse.wait() before returning

  Why: Zombie processes, resource leaks, unchecked exit codes
  See: spec/arch/backpressure.md (Mistake 4)
```

### Rule 5: subprocess.run Instead of Popen for Streaming

**Anti-pattern:**
```python
# Plugin wants to stream but uses run()
result = subprocess.run(cmd, stdin=sys.stdin, stdout=subprocess.PIPE)
for line in result.stdout.split('\n'):  # Already buffered!
    process(line)
```

**AST Detection:**
- Find subprocess.run() calls
- Check if used in streaming context (iterating over output)

**Error message:**
```
backpressure.md line 583: subprocess.run should be Popen for streaming
  plugin.py:55: result = subprocess.run(cmd, ...)
                         ^^^^^^^^^^^^^^^
  ❌ subprocess.run doesn't support streaming
  ✅ Fix: Use subprocess.Popen for concurrent execution

  See: spec/arch/backpressure.md (The Solution)
```

### Rule 6: Missing PEP 723 Dependencies

**Anti-pattern:**
```python
# In plugin file
import pandas  # Not declared in PEP 723!

# PEP 723 block missing or incomplete
# /// script
# requires-python = ">=3.11"
# dependencies = []  # ← pandas not listed!
# ///
```

**AST Detection:**
- Parse PEP 723 TOML block from docstring
- Extract all imports from AST
- Cross-check: imports not in stdlib and not in dependencies list

**Error message:**
```
PEP 723 dependency missing
  plugin.py:15: import pandas
                       ^^^^^^
  ❌ 'pandas' imported but not declared in dependencies
  ✅ Fix: Add to PEP 723 block:

  # /// script
  # dependencies = [
  #   "pandas>=2.0.0",
  # ]
  # ///
```

### Rule 7: Overly Broad Try-Catch

**Anti-pattern:**
```python
try:
    response = requests.get(url)
    data = response.json()
    # ... 20 more lines ...
    process_data(data)
    write_output(data)
    cleanup()
except json.JSONDecodeError as e:  # Only catches JSON error but wraps 20 lines!
    print(f"Error: {e}")
```

**AST Detection:**
- Find try-except blocks
- Count lines in try body
- Check if exception types are specific but body is large (>5 lines)

**Error message:**
```
Try-catch scope too broad
  plugin.py:45-68: try block spans 23 lines
  plugin.py:69: except json.JSONDecodeError:
                       ^^^^^^^^^^^^^^^^^^^
  ❌ Catching specific exception but wrapping 23 lines
  ✅ Fix: Narrow try block to just the line that can raise:

  try:
      data = response.json()  # Only this line
  except json.JSONDecodeError as e:
      # Handle error
```

### Rule 8: Using Threads Instead of Processes

**Anti-pattern:**
```python
import threading

def process_data():
    # ... data pipeline work ...

thread = threading.Thread(target=process_data)
thread.start()
```

**AST Detection:**
- Find imports of `threading`
- Find Thread() instantiations
- Flag as anti-pattern for data pipelines

**Error message:**
```
Using threads instead of processes for data pipeline
  plugin.py:12: import threading
  plugin.py:45: thread = threading.Thread(...)
                         ^^^^^^^^^^^^^^^^
  ❌ Threads don't provide parallelism or backpressure
  ✅ Fix: Use subprocess.Popen with pipes

  Why: Python GIL prevents CPU parallelism, no automatic backpressure
  See: spec/arch/backpressure.md (Async I/O vs Processes)
```

### Rule 9: Config Dict Pattern (Optional)

**Anti-pattern:**
```python
def reads(config: Optional[dict] = None):
    config = config or {}
    url = config.get("url")
    method = config.get("method", "GET")
    # ... 10 more .get() calls
```

**AST Detection:**
- Find function definitions with `config` parameter
- Check if function body does `config = config or {}`
- Count `.get()` calls on config

**Error message:**
```
Config dict pattern discouraged
  plugin.py:25: def reads(config: Optional[dict] = None):
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  plugin.py:26:     config = config or {}
  plugin.py:27-35:  8 config.get() calls found

  ⚠️  Consider: Use discrete function parameters instead
  ✅ Better: def reads(url: str, method: str = "GET", ...)

  Why: Simpler, type-safe, no dict building/unpacking
```

## CLI Interface

### Command Structure

```bash
# Check core JN code
jn check core

# Check all plugins (bundled + user)
jn check plugins

# Check everything (core + plugins)
jn check all

# Check specific plugin
jn check csv_
jn check jq_

# Verbose output
jn check plugins --verbose

# Only specific rules
jn check plugins --rules subprocess,backpressure

# Output format
jn check plugins --format json
```

### Target Resolution

**`jn check plugins`** scans:
- `jn_home/plugins/**/*.py` (bundled plugins)
- `~/.local/jn/plugins/**/*.py` (user plugins)
- `$JN_HOME/plugins/**/*.py` (project plugins, if set)

**`jn check core`** scans:
- `src/jn/**/*.py` (all core code)

**`jn check all`** scans:
- Everything (core + all plugins)

**`jn check csv_`** scans:
- Finds `csv_.py` in plugin search paths
- Checks only that file

### Output Format

**Text (default):**
```
$ jn check csv_

Checking: csv_ (jn_home/plugins/formats/csv_.py)

✅ Pass: No capture_output found
✅ Pass: No missing stdout.close()
❌ Fail: Missing dependency 'pandas'
  → csv_.py:15: import pandas

✅ Pass: No broad try-catch blocks

Summary: 1 violation found
Exit code: 1
```

**Multiple plugins:**
```
$ jn check plugins

Checking: csv_ (jn_home/plugins/formats/csv_.py)
  ✅ All checks passed

Checking: jq_ (jn_home/plugins/filters/jq_.py)
  ✅ All checks passed

Checking: http_ (jn_home/plugins/protocols/http_.py)
  ❌ 1 violation found

Summary: 2/3 plugins passed, 1 violation total
Exit code: 1
```

**JSON (for CI/CD):**
```json
{
  "plugin": "csv_",
  "violations": [
    {
      "rule": "missing_dependency",
      "severity": "error",
      "file": "csv_.py",
      "line": 15,
      "column": 7,
      "message": "'pandas' imported but not declared in dependencies",
      "fix": "Add 'pandas>=2.0.0' to PEP 723 dependencies"
    }
  ],
  "passed": 4,
  "failed": 1
}
```

## Implementation Plan

### Phase 1: Core Infrastructure
- [ ] Create `src/jn/checker/ast_checker.py` - AST traversal engine
- [ ] Create `src/jn/checker/report.py` - Error formatting
- [ ] Create `jn check` CLI command

### Phase 2: Subprocess Rules
- [ ] Detect subprocess.run with capture_output
- [ ] Detect missing stdout.close()
- [ ] Detect buffered reading (.read())
- [ ] Detect missing .wait()

### Phase 3: Dependency Rules
- [ ] Parse PEP 723 blocks
- [ ] Extract imports from AST
- [ ] Cross-check imports vs dependencies
- [ ] Handle stdlib detection

### Phase 4: Exception Rules
- [ ] Detect overly broad try-catch
- [ ] Measure try block size
- [ ] Check exception specificity

### Phase 5: Integration
- [ ] `jn plugin check` command
- [ ] Check all plugins
- [ ] Check core code
- [ ] CI/CD integration

## Testing Strategy

### Unit Tests
```python
def test_detect_capture_output():
    code = '''
result = subprocess.run(cmd, capture_output=True)
    '''
    violations = check_code(code, rules=['subprocess'])
    assert len(violations) == 1
    assert violations[0].rule == 'capture_output'
```

### Integration Tests
```python
def test_check_real_plugin():
    plugin_path = Path("jn_home/plugins/formats/csv_.py")
    report = check_plugin(plugin_path)
    assert report.passed > 0
```

### Regression Tests
```python
def test_jq_plugin_passes():
    """JQ plugin should pass all checks (it's been refactored)."""
    report = check_plugin("jn_home/plugins/filters/jq_.py")
    assert report.failed == 0
```

## Example: Real World Detection

### Bad Code
```python
# jn_home/plugins/formats/bad_example.py

import pandas  # Missing from dependencies!

def reads(config: Optional[dict] = None):
    config = config or {}
    url = config.get("url")

    # Anti-pattern: subprocess.run with capture_output
    result = subprocess.run(['curl', url], capture_output=True)

    # Anti-pattern: Reading all data
    all_data = result.stdout.decode()

    # Anti-pattern: Overly broad try-catch
    try:
        df = pandas.read_csv(StringIO(all_data))
        processed = df.to_dict('records')
        cleanup_temp_files()
        send_metrics()
    except ValueError as e:  # Only catches ValueError but wraps 4 operations!
        print(f"Error: {e}")

    for record in processed:
        yield record
```

### Checker Output
```
Checking: jn_home/plugins/formats/bad_example.py

❌ Missing PEP 723 dependency
  Line 3: import pandas
  Fix: Add 'pandas>=2.0.0' to dependencies

❌ subprocess.run with capture_output=True
  Line 10: result = subprocess.run(['curl', url], capture_output=True)
  Fix: Use subprocess.Popen with pipes for streaming
  See: spec/arch/backpressure.md (line 18)

❌ Reading all data before processing
  Line 13: all_data = result.stdout.decode()
  Fix: Stream incrementally: for line in process.stdout
  See: spec/arch/backpressure.md (line 360)

❌ Try-catch scope too broad
  Lines 16-21: try block spans 6 lines
  Line 22: except ValueError
  Fix: Narrow try block to just pandas.read_csv()

⚠️  Config dict pattern found
  Line 5: def reads(config: Optional[dict] = None)
  Consider: Use discrete parameters instead

Summary: 4 errors, 1 warning
Exit code: 1
```

### Fixed Code
```python
# jn_home/plugins/formats/good_example.py

# /// script
# dependencies = [
#   "pandas>=2.0.0",
# ]
# ///

import pandas

def reads(url: str):  # Discrete parameter
    # Correct: Popen for streaming
    fetch = subprocess.Popen(['curl', url], stdout=subprocess.PIPE)

    # Narrow try block
    try:
        df = pandas.read_csv(fetch.stdout)
    except ValueError as e:
        yield error_record("csv_parse_error", str(e))
        return

    # Stream results
    for record in df.to_dict('records'):
        yield record

    fetch.wait()
```

## Benefits

1. **Prevent backpressure violations** - Catch before production
2. **Enforce architecture** - Automated documentation compliance
3. **Faster code review** - Automated checks reduce human time
4. **Educational** - Error messages teach principles
5. **CI/CD integration** - Block bad code automatically
6. **Confidence** - Contributors know code is correct

## Future Enhancements

1. **Auto-fix mode** - `jn check --fix` applies corrections
2. **Custom rules** - Project-specific `.jncheck.toml`
3. **Performance analysis** - Estimate memory usage
4. **Security rules** - Detect command injection, path traversal
5. **Style rules** - Consistent formatting across plugins

## References

- spec/arch/backpressure.md - Anti-patterns source
- Python ast module - AST traversal
- ruff, pylint - Existing linters for inspiration
- mypy - Type checking patterns
