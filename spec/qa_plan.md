# QA Plan: Backpressure & Streaming

This document provides checklists for ensuring correct backpressure implementation in JN pipelines.

---

## Checklist 1: ✅ What to Look for in Good Backpressure Code

### Pipeline Construction

- [ ] **Uses `subprocess.Popen`** (never `subprocess.run` with `capture_output=True`)
  ```python
  # GOOD ✅
  proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)

  # BAD ❌
  result = subprocess.run(cmd, capture_output=True)
  ```

- [ ] **Chains processes with pipes** (stdin=prev.stdout)
  ```python
  # GOOD ✅
  reader = subprocess.Popen(cmd1, stdout=subprocess.PIPE)
  writer = subprocess.Popen(cmd2, stdin=reader.stdout)
  ```

- [ ] **Closes stdout in parent** after chaining (CRITICAL!)
  ```python
  # CRITICAL ✅
  reader = subprocess.Popen(cmd1, stdout=subprocess.PIPE)
  writer = subprocess.Popen(cmd2, stdin=reader.stdout)
  reader.stdout.close()  # ← Must be present!
  ```

- [ ] **Streams incrementally** (iterates over stdout, doesn't read all at once)
  ```python
  # GOOD ✅
  for line in proc.stdout:
      process(line)

  # BAD ❌
  all_data = proc.stdout.read()
  for line in all_data.split('\n'):
      process(line)
  ```

### Process Management

- [ ] **Calls `wait()` on all processes** before exit
  ```python
  proc.wait()
  ```

- [ ] **Checks return codes** for errors
  ```python
  if proc.returncode != 0:
      handle_error()
  ```

- [ ] **Reads stderr AFTER wait()** (not during streaming)
  ```python
  proc.wait()
  if proc.returncode != 0:
      error = proc.stderr.read()  # ✅ After wait
  ```

- [ ] **No zombie processes** (all procs have wait() called)

### Memory Characteristics

- [ ] **Constant memory usage** regardless of input size
  - Test: 10MB file uses ~1MB RAM
  - Test: 1GB file uses ~1MB RAM
  - Test: 10GB file uses ~1MB RAM

- [ ] **No accumulation in buffers**
  - No lists that grow with input size
  - No in-memory copies of entire datasets

### Early Termination Support

- [ ] **Handles downstream exit cleanly** (e.g., `| head -n 10`)
  ```python
  # When consumer exits early, SIGPIPE propagates:
  # head exits → reader gets SIGPIPE → stops processing
  ```

- [ ] **No deadlocks** when consumer exits early

- [ ] **Stops processing upstream** when downstream closes

---

## Checklist 2: 🚨 Warning Flags for Backpressure Issues

### Critical Red Flags

- [ ] ❌ **`subprocess.run(capture_output=True)`** - Buffers entire output in memory
- [ ] ❌ **`proc.stdout.read()`** - Reads all data at once (blocks until EOF)
- [ ] ❌ **Missing `prev_proc.stdout.close()`** - SIGPIPE won't propagate
- [ ] ❌ **`.communicate()`** - Buffers all stdout/stderr in memory
- [ ] ❌ **Storing all lines in a list** before processing

### Memory Accumulation Patterns

- [ ] ⚠️ **Growing buffers** - `buffer.append()` in loop without limit
  ```python
  # BAD ❌
  all_lines = []
  for line in proc.stdout:
      all_lines.append(line)  # Grows unbounded!
  ```

- [ ] ⚠️ **String concatenation** in loop
  ```python
  # BAD ❌
  result = ""
  for line in proc.stdout:
      result += line  # O(n²) memory copies
  ```

- [ ] ⚠️ **Multiple passes** requiring all data in memory
  ```python
  # BAD ❌
  lines = list(proc.stdout)  # Loads all into memory
  first_pass(lines)
  second_pass(lines)
  ```

### Process Management Issues

- [ ] ⚠️ **No `wait()` called** - Zombie processes
- [ ] ⚠️ **Reading stderr during streaming** - Can cause deadlock
  ```python
  # RISKY ⚠️
  for line in proc.stdout:
      if proc.stderr.read():  # Can block!
          ...
  ```

- [ ] ⚠️ **Process started but not tracked** - Resource leak

### Streaming Violations

- [ ] ⚠️ **Buffering before processing**
  ```python
  # BAD ❌
  data = proc.stdout.read()  # Waits for entire output
  process(data)
  ```

- [ ] ⚠️ **Non-streaming data structures** (JSON arrays, not NDJSON)
  ```python
  # BAD for streaming ❌
  {"users": [...]}  # Can't parse until ] received

  # GOOD for streaming ✅
  {"name": "Alice"}
  {"name": "Bob"}
  ```

### Testing Red Flags

- [ ] ⚠️ **Memory usage grows with input size** in tests
- [ ] ⚠️ **Timeout on large files** that should stream
- [ ] ⚠️ **`head -n 10` processes entire file** instead of stopping early
- [ ] ⚠️ **Processes don't exit** when downstream closes

---

## Checklist 3: 🐛 Known Issues & Edge Cases

### 1. Click Test Runner (Non-File Streams)

**Issue:** Click's `CliRunner` provides `StringIO` objects, not real file handles

**Detection:**
```python
try:
    sys.stdin.fileno()  # Fails for StringIO
except:
    # Must use subprocess.PIPE + write data
```

**Solution:**
```python
stdin_source, input_data, text_mode = _prepare_stdin_for_subprocess(stream)
proc = subprocess.Popen(cmd, stdin=stdin_source, text=text_mode)
if input_data:
    proc.stdin.write(input_data)
    proc.stdin.close()
```

**Status:** ✅ Handled in `_prepare_stdin_for_subprocess()` helper

### 2. SIGPIPE Not Propagating

**Issue:** Parent holds pipe reference → SIGPIPE doesn't reach producer

**Symptoms:**
- Upstream process doesn't exit when downstream exits
- `| head -n 10` downloads entire file
- Processes hang or become zombies

**Detection:**
```bash
# Test early termination
jn cat large.csv | head -n 10
# Should return quickly, not process entire file
```

**Root Cause:**
```python
# Missing this line:
reader.stdout.close()  # ← Without this, no SIGPIPE!
```

**Status:** ✅ Present in `pipeline.py:253`

### 3. Reading stderr During Streaming

**Issue:** Can cause deadlock if stderr pipe fills

**Problematic Pattern:**
```python
# BAD ❌
for line in proc.stdout:
    process(line)
    if error_condition:
        error = proc.stderr.read()  # Can block forever!
```

**Why:** stderr pipe buffer (~64KB) can fill, causing process to block

**Solution:**
```python
# GOOD ✅
for line in proc.stdout:
    process(line)

proc.wait()
if proc.returncode != 0:
    error = proc.stderr.read()  # Safe after wait()
```

**Status:** ✅ All stderr reads happen after `wait()`

### 4. Text Mode vs Binary Mode Mismatch

**Issue:** Mixing text and binary modes causes encoding errors

**Detection:**
```python
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
# Later:
data = proc.stdout.read()  # Returns str, not bytes
```

**Edge Case:**
```python
# When feeding data to stdin:
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=False)
proc.stdin.write("string")  # TypeError! Expects bytes
```

**Solution:** Be consistent with `text=` parameter

**Status:** ✅ Handled via `text_mode` flag in helpers

### 5. Process Exit Order

**Issue:** Waiting for processes in wrong order can cause hangs

**Problematic:**
```python
# BAD ❌
reader.wait()  # Might block if writer hasn't consumed output
writer.wait()
```

**Why:** Reader can't exit if writer hasn't consumed all output

**Solution:**
```python
# GOOD ✅
writer.wait()  # Wait for consumer first
reader.wait()  # Then producer
```

**Status:** ✅ Correct order in `pipeline.py:256-257`

### 6. File Descriptor Leaks

**Issue:** Opening files in reader but not closing them

**Detection:**
```bash
lsof -p $PID | wc -l  # Count open file descriptors
```

**Problematic:**
```python
# BAD ❌
infile = open(source)
proc = subprocess.Popen(cmd, stdin=infile)
proc.wait()
# infile never closed!
```

**Solution:**
```python
# GOOD ✅
with open(source) as infile:
    proc = subprocess.Popen(cmd, stdin=infile)
    proc.wait()
# Auto-closed by context manager
```

**Status:** ✅ Uses context managers (`with` statements)

### 7. Tail Buffering Requirements

**Issue:** `tail -n N` requires buffering last N lines (not true streaming)

**Why:** Can't know which lines are "last" until EOF

**Memory Usage:** O(N) where N = number of lines to keep

**Implementation:**
```python
# Uses deque with maxlen for circular buffer
buffer = deque(maxlen=n)
for line in input_stream:
    buffer.append(line)  # Only keeps last N
```

**Status:** ✅ Correct implementation in `streaming.py:38`

### 8. Plugin Failures Don't Stop Pipeline

**Issue:** If reader fails, writer might hang waiting for input

**Detection:** Check both return codes

**Solution:**
```python
writer.wait()
reader.wait()

# Check both ✅
if writer.returncode != 0:
    raise PipelineError(f"Writer error: {writer.stderr.read()}")
if reader.returncode != 0:
    raise PipelineError(f"Reader error: {reader.stderr.read()}")
```

**Status:** ✅ Both checked in `pipeline.py:260-266`

### 9. Binary Data in Text Mode

**Issue:** Some formats (images, binary files) can't use text mode

**Detection:**
```python
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
# If output contains binary data → UnicodeDecodeError
```

**Solution:** Use binary mode for binary data
```python
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=False)
```

**Status:** ⚠️ Currently assumes text for NDJSON (acceptable for current scope)

### 10. Large Line Buffering

**Issue:** Python's text mode buffers lines - very long lines can cause issues

**Scenario:** 1GB single-line JSON object

**Workaround:** Process in binary mode with manual newline detection

**Status:** ⚠️ Not handled (acceptable - NDJSON should have line breaks)

---

## Testing Backpressure

### Unit Tests

```python
def test_early_termination(people_csv):
    """Verify pipeline stops when downstream exits."""
    # Use head to force early termination
    result = invoke(["cat", str(people_csv)])
    # Process first 2 lines, discard rest
    lines = result.output.split('\n')[:2]
    assert len(lines) == 2

def test_constant_memory():
    """Verify memory doesn't grow with file size."""
    # Would require integration test with memory profiling
    pass
```

### Integration Tests

```bash
# Test 1: Early termination
jn cat large-file.csv | head -n 10
# Should return quickly (not process entire file)

# Test 2: Memory usage
/usr/bin/time -v jn cat 1GB-file.csv | head -n 10
# Check "Maximum resident set size" (should be ~10MB, not 1GB)

# Test 3: Process cleanup
jn cat large-file.csv | head -n 10 &
sleep 1
ps aux | grep jn
# Should show no zombie processes
```

### Monitoring Tests

```bash
# Monitor network during early termination
nethogs &
jn cat https://example.com/huge.xlsx | head -n 10
# Network should stop after ~10 rows downloaded

# Monitor file descriptors
lsof -p $(pgrep -f 'jn cat') | wc -l
# Should be small constant number (not growing)
```

---

## Common Anti-Patterns to Avoid

### 1. Double Buffering
```python
# BAD ❌
data = proc.stdout.read()  # Buffers entire output
proc2 = subprocess.Popen(cmd2, input=data)  # Buffers again
```

### 2. Unnecessary Conversion
```python
# BAD ❌
lines = list(proc.stdout)  # Converts generator to list
for line in lines:
    process(line)

# GOOD ✅
for line in proc.stdout:  # Keep as generator
    process(line)
```

### 3. Premature Optimization
```python
# BAD ❌ - Trying to be "clever"
chunk_size = 64 * 1024
while True:
    chunk = proc.stdout.read(chunk_size)
    if not chunk:
        break
    # Process in chunks...

# GOOD ✅ - Let Python handle it
for line in proc.stdout:
    process(line)
```

### 4. Mixing Paradigms
```python
# BAD ❌
async def process():
    proc = subprocess.Popen(...)  # Subprocess + async is messy
    await something()
```

---

## Reference Implementation

**File:** `src/jn/core/pipeline.py:234-267` (convert function)

This is the canonical example of correct backpressure:

```python
def convert(source, dest, plugin_dir, cache_path):
    # Load plugins
    plugins, registry = _load_plugins_and_registry(plugin_dir, cache_path)
    reader_plugin = plugins[registry.match(source)]
    writer_plugin = plugins[registry.match(dest)]

    # Execute two-stage pipeline
    with open(source) as infile, open(dest, "w") as outfile:
        # Stage 1: Reader
        reader = subprocess.Popen(
            [sys.executable, reader_plugin.path, "--mode", "read"],
            stdin=infile,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Stage 2: Writer
        writer = subprocess.Popen(
            [sys.executable, writer_plugin.path, "--mode", "write"],
            stdin=reader.stdout,  # ← Pipe chaining
            stdout=outfile,
            stderr=subprocess.PIPE,
        )

        # CRITICAL: Enable SIGPIPE backpressure
        reader.stdout.close()

        # Wait in correct order
        writer.wait()  # Consumer first
        reader.wait()  # Producer second

        # Check both for errors
        if writer.returncode != 0:
            raise PipelineError(f"Writer error: {writer.stderr.read()}")
        if reader.returncode != 0:
            raise PipelineError(f"Reader error: {reader.stderr.read()}")
```

**Why this is correct:**
1. ✅ Uses Popen (not run)
2. ✅ Chains with stdin=reader.stdout
3. ✅ Closes reader.stdout in parent
4. ✅ Waits in correct order (consumer first)
5. ✅ Checks both return codes
6. ✅ Reads stderr after wait()
7. ✅ Uses context managers for files

---

## Quick Reference Card

| ✅ DO | ❌ DON'T |
|-------|----------|
| `subprocess.Popen(cmd, stdout=PIPE)` | `subprocess.run(cmd, capture_output=True)` |
| `reader.stdout.close()` after chaining | Leave stdout open in parent |
| `for line in proc.stdout:` | `all_data = proc.stdout.read()` |
| `writer.wait(); reader.wait()` | `reader.wait(); writer.wait()` |
| Read stderr after `wait()` | Read stderr during streaming |
| Use context managers | Manual file handling |
| Check both returncodes | Assume success |
| Stream incrementally | Buffer then process |

---

## Automated Checks

```bash
# Check 1: No subprocess.run with capture_output
grep -r "subprocess.run.*capture_output" src/
# Should return nothing

# Check 2: All Popen calls close stdout
grep -A 5 "stdin=.*\.stdout" src/ | grep "\.stdout\.close()"
# Should find all cases

# Check 3: No .read() on stdout during streaming
grep -r "\.stdout\.read()" src/
# Should return nothing (or only after wait())

# Check 4: All Popen calls have wait()
# Manual review needed
```

---

## See Also

- `spec/arch/backpressure.md` - Detailed backpressure explanation
- `src/jn/core/pipeline.py` - Reference implementation
- `CLAUDE.md` - Project architecture guidelines
