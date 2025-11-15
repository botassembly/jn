# Popen + Pipes: Streaming with Automatic Backpressure

## Executive Summary

JN uses **Unix processes connected via pipes** for streaming data pipelines. This provides:
- ✅ **Automatic backpressure** via OS pipe buffers
- ✅ **True parallelism** (multi-CPU, not cooperative multitasking)
- ✅ **Zero async complexity** (no async/await syntax)
- ✅ **Clean shutdown** via SIGPIPE signal propagation
- ✅ **Low memory usage** (~64KB pipe buffers, not GB)

This document explains why this architecture is superior to alternatives (async I/O, threading, buffering) and how to implement it correctly.

---

## The Problem: Memory Buffering

### Bad Pattern: subprocess.run with capture_output

```python
# DON'T DO THIS: Buffers entire file in memory
result = subprocess.run(['curl', 'http://example.com/1GB.xlsx'], capture_output=True)
# ↑ Stores 1GB in result.stdout (1GB RAM!)

reader_result = subprocess.run(['xlsx_reader'], input=result.stdout)
# ↑ Stores another 1GB in reader_result.stdout (2GB RAM total!)

# For 1GB file → 2GB RAM used!
```

**Problems:**
- Memory usage: O(file_size) × number_of_stages
- Large files (>1GB) cause OOM (out of memory)
- No parallelism (sequential execution)
- No backpressure (downloads full file even if you only need first 10 rows)

---

## The Solution: Popen with Pipes

### Good Pattern: Streaming with Backpressure

```python
# CORRECT: Stream with OS pipes
fetch = subprocess.Popen(['curl', url], stdout=subprocess.PIPE)
reader = subprocess.Popen(['xlsx_reader'], stdin=fetch.stdout, stdout=subprocess.PIPE)

# CRITICAL: Close fetch stdout in parent process
fetch.stdout.close()  # Enables SIGPIPE propagation

# Stream output incrementally
for line in reader.stdout:
    process_line(line)  # Pull-based: reader controls flow

# Wait for completion
reader.wait()
fetch.wait()

# For 1GB file → ~64KB RAM used!
```

**Benefits:**
- Memory usage: O(pipe_buffer) ≈ 64KB
- Processes run in parallel (concurrent downloading + parsing)
- Automatic backpressure (slow reader → fetch pauses)
- Clean shutdown (SIGPIPE propagates backward)

---

## How Backpressure Works

### OS Pipe Buffer Mechanics

```
┌──────────┐       ┌──────────┐       ┌──────────┐
│  curl    │──────▶│ xlsx     │──────▶│  head    │
│ (fetch)  │ pipe  │ reader   │ pipe  │ -n 10    │
└──────────┘ 64KB  └──────────┘       └──────────┘
     ↑                  ↑                   ↓
     │                  │              Reads 10 lines
     │                  │              then EXITS
     │                  │
  Blocks when       Blocks when
  pipe is full      stdin empty
     │                  │
     └──────────────────┘
      Automatic Backpressure!
```

### Step-by-Step Flow

1. **curl starts downloading** → writes to pipe
2. **Pipe buffer fills** to ~64KB (OS limit)
3. **curl blocks** (write() syscall blocks until pipe has space)
4. **xlsx_reader reads from stdin** → processes data → writes NDJSON to pipe
5. **As reader consumes data** → pipe has space → curl resumes
6. **If head exits after 10 lines:**
   - Reader's stdout pipe closes
   - Reader gets **SIGPIPE** → exits
   - Curl gets **SIGPIPE** → stops downloading
   - **Zero memory accumulation!**

**This is automatic - no code needed for flow control!**

---

## Critical Implementation Detail: stdout.close()

### Why You Must Close fetch.stdout in Parent

```python
# Create pipeline
fetch = subprocess.Popen(['curl', url], stdout=subprocess.PIPE)
reader = subprocess.Popen(['xlsx_reader'], stdin=fetch.stdout, stdout=subprocess.PIPE)

# CRITICAL LINE:
fetch.stdout.close()  # ← Without this, SIGPIPE doesn't work!
```

### Without close() - Deadlock Scenario

```
Parent process
    ↓ holds reference
┌────────┐
│ Fetch  │──→ Pipe ──→ Reader
└────────┘      ↑
                │
         Parent also has reference!
```

**What happens:**
1. Reader exits early (e.g., head -n 10)
2. Reader's stdin closes
3. **But parent still holds a reference to the pipe**
4. Fetch doesn't receive SIGPIPE (pipe not fully closed)
5. **Fetch keeps writing to pipe → deadlock or memory accumulation!**

### With close() - Clean Shutdown

```
Parent process (no reference)

┌────────┐
│ Fetch  │──→ Pipe ──→ Reader
└────────┘
```

**What happens:**
1. Reader exits early
2. Reader's stdin closes
3. **No other references to pipe exist**
4. **Fetch receives SIGPIPE** signal
5. Fetch exits cleanly
6. **This is the Unix way!**

---

## Memory Comparison

### Large File (1GB XLSX, 10M rows)

| Approach | Memory Usage | Time | Parallelism |
|----------|-------------|------|-------------|
| **subprocess.run (bad)** | 2GB | 90s | None (sequential) |
| **Popen + pipes (good)** | ~1MB | 90s | Yes (concurrent) |
| **Popen + pipes + head -n 10 (excellent)** | ~1MB | <1s | Yes + early termination! |

**For the head -n 10 case:**
- subprocess.run: Downloads 1GB, parses 1GB, returns 10 rows (2GB RAM, 90s)
- Popen + pipes: Downloads ~1KB, parses ~1KB, returns 10 rows (1MB RAM, <1s)

**2000x memory reduction, 90x time reduction!**

---

## Real-World Example: jn cat with Early Termination

```bash
$ jn cat https://example.com/massive.xlsx | head -n 10
```

### What Happens (Popen + pipes)

```
1. jn spawns: curl → xlsx_reader → head
2. curl starts downloading, writes to pipe
3. xlsx_reader reads, parses, writes NDJSON to pipe
4. head reads 10 lines, then EXITS
5. xlsx_reader gets SIGPIPE (stdout closed) → EXITS
6. curl gets SIGPIPE (reader exited) → STOPS downloading
7. Total data transferred: ~10 rows worth (~1KB)
```

**Automatic backpressure!** Downstream (head) controls how much upstream (curl) downloads.

### What Would Happen (subprocess.run buffering)

```
1. jn runs: curl (capture_output=True)
2. curl downloads ENTIRE 1GB file → stores in memory
3. jn runs: xlsx_reader (input=1GB_data)
4. xlsx_reader parses ENTIRE 1GB → stores in memory
5. jn runs: head (input=parsed_data)
6. head reads 10 lines, discards rest
7. Total memory: 2GB, Total time: 90s
```

**No backpressure!** Processes entire file even though only 10 rows needed.

---

## Code Examples

### Pattern 1: Simple Pipeline (2 stages)

```python
def run_pipeline(url):
    """Fetch URL → Parse → Output NDJSON."""

    # Stage 1: Fetch
    fetch = subprocess.Popen(
        ['curl', '-sL', url],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Stage 2: Parse
    parser = subprocess.Popen(
        ['xlsx_reader'],
        stdin=fetch.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # CRITICAL: Close fetch stdout in parent
    fetch.stdout.close()

    # Stream output (pull-based)
    for line in parser.stdout:
        yield line.decode('utf-8')

    # Wait for processes
    parser.wait()
    fetch.wait()

    # Check errors
    if fetch.returncode != 0:
        raise Exception(f"Fetch failed: {fetch.stderr.read()}")
    if parser.returncode != 0:
        raise Exception(f"Parse failed: {parser.stderr.read()}")
```

### Pattern 2: Multi-Stage Pipeline (N stages)

```python
def run_multi_stage_pipeline(stages):
    """Run N-stage pipeline with automatic backpressure."""

    processes = []

    # Start all processes, chaining stdin/stdout
    for i, (cmd, stdin_source) in enumerate(stages):
        is_first = (i == 0)
        is_last = (i == len(stages) - 1)

        # Determine stdin
        if is_first:
            stdin = None  # First stage reads from its default
        else:
            stdin = processes[-1].stdout  # Chain from previous

        # Determine stdout
        if is_last:
            stdout = subprocess.PIPE  # Capture for return
        else:
            stdout = subprocess.PIPE  # Pipe to next stage

        # Start process
        proc = subprocess.Popen(
            cmd,
            stdin=stdin,
            stdout=stdout,
            stderr=subprocess.PIPE
        )
        processes.append(proc)

        # CRITICAL: Close previous stdout
        if i > 0:
            processes[i-1].stdout.close()

    # Stream output from last stage
    for line in processes[-1].stdout:
        yield line

    # Wait for all
    for proc in processes:
        proc.wait()
```

### Pattern 3: Plugin with Popen (jq filter)

```python
def run(config):
    """Filter NDJSON with jq (streaming)."""

    query = config.get('query', '.')

    # Stream stdin → jq → stdout (no buffering!)
    jq_process = subprocess.Popen(
        ['jq', '-c', query],
        stdin=sys.stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Stream output
    for line in jq_process.stdout:
        yield json.loads(line)

    # Check for errors
    returncode = jq_process.wait()
    if returncode != 0:
        stderr = jq_process.stderr.read()
        raise Exception(f"jq failed: {stderr}")
```

---

## Common Mistakes

### Mistake 1: Forgetting to Close stdout

```python
# BAD: No close - SIGPIPE won't propagate
fetch = subprocess.Popen(['curl', url], stdout=subprocess.PIPE)
parser = subprocess.Popen(['parser'], stdin=fetch.stdout, stdout=subprocess.PIPE)
# Missing: fetch.stdout.close()

for line in parser.stdout:
    print(line)
```

**Problem:** If parser exits early, fetch doesn't get SIGPIPE → keeps running.

### Mistake 2: Using capture_output=True

```python
# BAD: Buffers entire output in memory
result = subprocess.run(['curl', url], capture_output=True)
data = result.stdout  # Entire file in RAM!
```

**Problem:** No streaming, no backpressure, high memory usage.

### Mistake 3: Reading All Data Before Processing

```python
# BAD: Buffers before processing
all_data = process.stdout.read()  # Reads entire output
for line in all_data.split('\n'):
    process_line(line)
```

**Problem:** Defeats streaming - loads all data into memory first.

**Fix:**
```python
# GOOD: Stream line by line
for line in process.stdout:
    process_line(line)
```

### Mistake 4: Not Waiting for Processes

```python
# BAD: Starts processes but doesn't wait
fetch = subprocess.Popen(...)
parser = subprocess.Popen(...)
# Missing: wait() calls
```

**Problem:** Zombie processes, resource leaks, exit codes not checked.

**Fix:**
```python
fetch.wait()
parser.wait()
if fetch.returncode != 0:
    handle_error()
```

---

## Async I/O vs Processes

### Why Not asyncio?

**Async I/O (asyncio) is designed for:**
- Single-threaded event loop concurrency
- Thousands of concurrent I/O operations (web servers)
- Cooperative multitasking

**Processes + Pipes are better for data pipelines because:**

| Feature | Processes + Pipes | Async I/O |
|---------|------------------|-----------|
| **Concurrency** | True parallelism (multi-CPU) | Cooperative (single thread) |
| **Backpressure** | Automatic (OS pipes block) | Manual (Queues, flow control) |
| **Memory** | O(pipe_buffer) ~64KB | O(buffer) - manual tuning |
| **Complexity** | Simple (no async/await) | Complex (async everywhere) |
| **Isolation** | Separate process memory | Shared memory (harder bugs) |
| **Debugging** | Standard tools (ps, strace) | Async-specific debugging |
| **Shutdown** | SIGPIPE (automatic) | Manual cancellation logic |
| **Composability** | Unix pipes (universal) | Async-specific APIs |

**Example Complexity:**

```python
# Processes + Pipes (simple)
fetch = subprocess.Popen(['curl', url], stdout=subprocess.PIPE)
parser = subprocess.Popen(['parser'], stdin=fetch.stdout, stdout=subprocess.PIPE)
fetch.stdout.close()
for line in parser.stdout:
    process(line)

# Async I/O (complex)
async def fetch_and_parse(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            async for chunk in response.content.iter_chunked(64*1024):
                # Manual flow control needed here
                await queue.put(chunk)
                if queue.qsize() > MAX_QUEUE_SIZE:
                    await asyncio.sleep(0)  # Yield control

    async def parse():
        while True:
            chunk = await queue.get()
            # ... parse ...

    # Need to coordinate fetch and parse tasks
    await asyncio.gather(fetch_task, parse_task)
```

**Processes are simpler AND more robust!**

---

## Performance Characteristics

### Memory Usage

| File Size | subprocess.run | Popen + pipes |
|-----------|---------------|---------------|
| 10 MB | 20 MB | ~1 MB |
| 100 MB | 200 MB | ~1 MB |
| 1 GB | **2 GB (OOM!)** | ~1 MB |
| 10 GB | **20 GB (crash)** | ~1 MB |

**Memory usage is constant regardless of file size!**

### Throughput

Processes + pipes can achieve **near-line-rate throughput** because:
- Multiple stages run in parallel
- OS scheduler distributes work across CPUs
- Pipe buffers minimize context switching

**Example:** 3-stage pipeline on 4-core machine
```
CPU1: curl (downloading)
CPU2: xlsx_reader (parsing)
CPU3: jq (filtering)
CPU4: csv_writer (outputting)

All running simultaneously!
```

### Latency

**Time to first output:**
- subprocess.run: Must download + parse entire file
- Popen + pipes: First output as soon as first record parsed

**Example:** 1GB file, head -n 10
- subprocess.run: 90 seconds (full download + parse)
- Popen + pipes: <1 second (stops after 10 rows)

---

## Testing Backpressure

### Verify Automatic Backpressure

```bash
# Test 1: Early termination
$ jn cat https://example.com/huge-file.xlsx | head -n 10
# Should return quickly (not download full file)

# Test 2: Monitor processes
$ jn cat https://example.com/huge-file.xlsx | head -n 10 &
$ watch -n 0.1 'ps aux | grep curl'
# curl should disappear quickly after head exits

# Test 3: Network monitoring
$ nethogs  # Monitor network usage
$ jn cat https://example.com/huge-file.xlsx | head -n 10
# Network usage should stop after ~10 rows downloaded
```

### Verify Memory Usage

```bash
# Monitor memory during pipeline
$ /usr/bin/time -v jn cat https://example.com/1GB-file.xlsx | head -n 10

# Look for:
# Maximum resident set size: Should be ~10MB (not 1GB!)
```

---

## When Streaming Doesn't Work

### Format Constraints

Some formats **require all data upfront:**

1. **CSV writer** - Needs all column names for header
2. **JSON array writer** - Needs `[...]` wrapping all elements
3. **XLSX writer** - ZIP archive requires all data before writing

**Solution:** These necessarily buffer. Alternative: Use streaming formats (NDJSON, streaming CSV).

### ZIP Archives (XLSX)

XLSX is a ZIP file containing XML:
- Must download full ZIP before extracting
- Can stream rows after loading

**Current approach:** Buffer file in memory (acceptable for <100MB files)

**Future option:** Stream to temp file for large files (>1GB)

---

## Best Practices

### ✅ DO

1. **Use Popen for pipelines**
   ```python
   subprocess.Popen(cmd, stdin=stdin, stdout=subprocess.PIPE)
   ```

2. **Close stdout in parent**
   ```python
   prev_process.stdout.close()
   ```

3. **Stream incrementally**
   ```python
   for line in process.stdout:
       yield line
   ```

4. **Wait for processes**
   ```python
   process.wait()
   if process.returncode != 0:
       handle_error()
   ```

5. **Check stderr for errors**
   ```python
   stderr = process.stderr.read()
   ```

### ❌ DON'T

1. **Don't use subprocess.run for streaming**
   ```python
   # NO: result = subprocess.run(cmd, capture_output=True)
   ```

2. **Don't buffer before processing**
   ```python
   # NO: all_data = process.stdout.read()
   ```

3. **Don't forget to close stdout**
   ```python
   # NO: Missing fetch.stdout.close()
   ```

4. **Don't use threads instead of processes**
   - Python GIL kills parallelism
   - No automatic backpressure
   - Shared memory bugs

5. **Don't use async for data pipelines**
   - More complex
   - No real benefit over processes
   - Manual flow control

---

## Summary

**Unix processes connected via pipes provide:**

✅ **Automatic backpressure** - OS pipe buffers block when full
✅ **Low memory** - ~64KB per pipe, not GB
✅ **Parallelism** - Multi-CPU execution
✅ **Simplicity** - No async syntax
✅ **Robustness** - Isolated memory, SIGPIPE shutdown
✅ **Composability** - Universal Unix interface

**Critical implementation:**
```python
# Always use Popen
process = subprocess.Popen(cmd, stdout=subprocess.PIPE)

# Always close stdout in parent
prev_process.stdout.close()  # Enables SIGPIPE!

# Always stream incrementally
for line in process.stdout:
    yield line
```

**This is the Unix way - simple, robust, efficient!**

---

## References

- JN executor.py: Reference implementation
- JN plugins/http/s3_get.py: Streaming transport example
- JN plugins/filters/jq_filter.py: Streaming filter example
- Unix Programming FAQ: Pipes and SIGPIPE
- Python subprocess documentation: Popen
