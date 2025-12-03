# Streaming and Backpressure

> **Purpose**: Why JN uses processes and pipes, and how this enables constant-memory streaming.

---

## The Memory Problem

Traditional data processing buffers entire files:

```python
# Typical approach (BAD)
data = requests.get(url).content          # 1GB in memory
records = parse_csv(data)                  # Another 1GB
filtered = [r for r in records if r['x'] > 10]  # Yet another GB
write_json(filtered, output)              # Peak: 3GB+ RAM
```

For a 1GB file:
- Memory: 3GB+ (entire file × number of stages)
- Latency: Wait for full download before any output
- No early termination: `head -n 10` still processes everything

---

## The Solution: Pipes with Backpressure

JN uses Unix processes connected by pipes:

```bash
jn cat data.csv | jn filter '.x > 10' | jn put output.json
```

Becomes three processes:

```
┌─────────┐   pipe   ┌─────────┐   pipe   ┌─────────┐
│   csv   │─────────▶│   zq    │─────────▶│  json   │
│  read   │  64KB    │ filter  │  64KB    │  write  │
└─────────┘  buffer  └─────────┘  buffer  └─────────┘
```

For a 1GB file:
- Memory: ~1MB (pipe buffers only)
- Latency: First output appears immediately
- Early termination: `head -n 10` stops everything

---

## How Pipe Buffers Work

### OS Pipe Mechanics

Unix pipes have a kernel buffer (~64KB on Linux):

```
Writer Process                    Reader Process
      │                                 │
      ▼                                 ▼
   write() ──▶ ┌──────────────┐ ◀── read()
               │  Pipe Buffer │
               │   (~64KB)    │
               └──────────────┘
```

**Key behaviors**:

1. **Write blocks when full**: If buffer is full, `write()` blocks until reader consumes data
2. **Read blocks when empty**: If buffer is empty, `read()` blocks until writer produces data
3. **Automatic flow control**: No manual coordination needed

### Backpressure in Action

```
Fast producer, slow consumer:

┌─────────┐        ┌─────────┐        ┌─────────┐
│  curl   │───────▶│ parser  │───────▶│  slow   │
│  fast   │        │ medium  │        │consumer │
└─────────┘        └─────────┘        └─────────┘

1. curl writes data to pipe
2. Pipe buffer fills up (64KB)
3. curl blocks on write() ← BACKPRESSURE
4. slow consumer reads some data
5. Pipe has space, curl resumes
6. Cycle repeats
```

**No data is lost. No memory grows. The OS handles everything.**

---

## SIGPIPE and Early Termination

When a downstream process exits, SIGPIPE propagates upstream:

```bash
jn cat huge.csv | head -n 10
```

What happens:

```
1. csv plugin starts reading huge.csv
2. csv writes records to stdout (pipe)
3. head reads 10 records
4. head exits (closes stdin)
5. Pipe reader is gone
6. csv's next write() fails with SIGPIPE
7. csv exits immediately
8. Total data processed: ~10 records
```

**A 10GB file with `head -n 10` processes only ~10 records worth of data.**

### The Critical `stdout.close()` Pattern

When orchestrating pipelines, you must close pipe references:

```python
# Orchestrator spawns two processes
reader = subprocess.Popen(['csv', '--mode=read'], stdout=subprocess.PIPE)
writer = subprocess.Popen(['json', '--mode=write'], stdin=reader.stdout)

# CRITICAL: Close reader.stdout in parent
reader.stdout.close()  # Without this, SIGPIPE won't propagate!

writer.wait()
reader.wait()
```

**Why?** The pipe stays open as long as anyone holds a reference. The parent holds a reference via `reader.stdout`. Closing it allows SIGPIPE to reach the reader when the writer exits.

---

## Performance Characteristics

### Memory Usage

| File Size | Buffered Approach | JN (Streaming) |
|-----------|-------------------|----------------|
| 10 MB | ~30 MB | ~1 MB |
| 100 MB | ~300 MB | ~1 MB |
| 1 GB | ~3 GB (OOM risk) | ~1 MB |
| 10 GB | ~30 GB (crash) | ~1 MB |

**Memory is constant regardless of file size.**

### Latency

| Scenario | Buffered | Streaming |
|----------|----------|-----------|
| First output | After full download | Immediately |
| `head -n 10` on 1GB | 90 seconds | < 1 second |
| Sampling large API | Full response | First page only |

**Streaming provides immediate feedback.**

### Throughput

Pipelines run stages in parallel:

```
CPU 1: ████████ fetch (I/O bound)
CPU 2:   ████████ decompress (CPU bound)
CPU 3:     ████████ parse (CPU bound)
CPU 4:       ████████ filter (CPU bound)
```

All stages execute simultaneously. Total time ≈ slowest stage, not sum of stages.

---

## Why Not Async?

Async I/O (`asyncio`) is designed for different problems:

| Feature | Processes + Pipes | Async I/O |
|---------|-------------------|-----------|
| **Parallelism** | True multi-CPU | Single thread, cooperative |
| **Backpressure** | Automatic (OS pipes) | Manual (queues, flow control) |
| **Memory** | O(buffer) ~64KB | O(queue) - must tune |
| **Complexity** | Simple (no async/await) | Complex (async everywhere) |
| **Isolation** | Separate memory | Shared memory (harder bugs) |
| **Debugging** | Standard tools (ps, strace) | Async-specific debugging |
| **Shutdown** | SIGPIPE (automatic) | Manual cancellation |

### Async Complexity Example

```python
# Async approach (COMPLEX)
async def fetch_and_parse(url):
    queue = asyncio.Queue(maxsize=10)  # Manual backpressure!

    async def fetch():
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                async for chunk in response.content:
                    await queue.put(chunk)  # Blocks if queue full
        await queue.put(None)  # Signal done

    async def parse():
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            # Parse chunk...

    await asyncio.gather(fetch(), parse())
```

vs.

```python
# Process approach (SIMPLE)
fetch = subprocess.Popen(['curl', url], stdout=subprocess.PIPE)
parse = subprocess.Popen(['parser'], stdin=fetch.stdout, stdout=subprocess.PIPE)
fetch.stdout.close()

for line in parse.stdout:
    print(line)
```

**Processes are simpler and more robust.**

---

## Why Not Threads?

Python threads have fundamental limitations:

### Global Interpreter Lock (GIL)

Python's GIL prevents true parallel execution:

```python
# Threads (LIMITED)
def parse(data):
    # CPU-bound parsing
    # Only one thread runs at a time due to GIL!

threads = [Thread(target=parse, args=(chunk,)) for chunk in chunks]
# Slower than single-threaded due to GIL overhead
```

### Shared Memory Bugs

Threads share memory, causing subtle bugs:

```python
# Shared state (DANGEROUS)
results = []

def worker(data):
    result = process(data)
    results.append(result)  # Race condition!
```

### Processes Avoid Both

```
Process 1        Process 2        Process 3
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Memory  │     │ Memory  │     │ Memory  │
│ (isolated)│   │ (isolated)│   │ (isolated)│
└─────────┘     └─────────┘     └─────────┘
     │               │               │
     └───── Pipe ────┴───── Pipe ────┘
              (only interface)
```

- No GIL (true parallelism)
- No shared memory (no races)
- Clean interface (pipes only)

---

## When Streaming Doesn't Work

Some formats require buffering:

### Write Modes That Buffer

| Format | Why It Buffers |
|--------|----------------|
| JSON array | Needs `[...]` wrapping |
| XLSX | ZIP archive requires all data |
| CSV (write) | May need all columns for header |

**Solution**: Use streaming formats (NDJSON, streaming CSV) where possible.

### Joins That Buffer

Hash joins buffer one side:

```bash
jn cat large.csv | jn join small.csv --on id
```

- `small.csv` is fully loaded (buffered)
- `large.csv` streams through

**Solution**: Put smaller dataset on right side of join.

### Aggregations That Buffer

Full aggregations need all data:

```bash
jn cat data.csv | jn filter -s 'sum(.amount)'
```

Must read all records to compute sum.

**Solution**: Use windowed aggregations where possible.

---

## Testing Backpressure

### Verify Early Termination

```bash
# Should complete in < 1 second (not download full file)
time jn cat https://example.com/huge.csv | head -n 10
```

### Monitor Network

```bash
# Watch network traffic
nethogs &
jn cat https://example.com/huge.csv | head -n 10
# Network should stop after ~10 records
```

### Check Memory

```bash
# Monitor peak memory
/usr/bin/time -v jn cat huge.csv | jn filter '.x > 10' | head -n 100
# Maximum resident set should be ~10MB, not file size
```

### Verify SIGPIPE Propagation

```bash
# Run in background, watch processes
jn cat huge.csv | head -n 10 &
watch -n 0.1 'ps aux | grep jn'
# All jn processes should exit shortly after head exits
```

---

## Implementation Checklist

### For Orchestrators

1. **Spawn with Popen**: `subprocess.Popen(..., stdout=subprocess.PIPE)`
2. **Chain stdin/stdout**: `next.stdin = prev.stdout`
3. **Close parent references**: `prev.stdout.close()` after spawning next stage
4. **Wait for completion**: `process.wait()` for all processes
5. **Check exit codes**: Non-zero indicates error

### For Plugins

1. **Stream output**: Write records as produced, don't buffer
2. **Handle SIGPIPE**: Exit gracefully (exit code 141 is normal)
3. **Flush on exit**: Ensure all data is written before exit
4. **Report errors to stderr**: Don't corrupt stdout with error messages

### Anti-Patterns to Avoid

```python
# DON'T: Buffer all output
all_data = process.stdout.read()  # Loads entire output into memory

# DO: Stream line by line
for line in process.stdout:
    yield line

# DON'T: Use capture_output
result = subprocess.run(['cmd'], capture_output=True)  # Buffers everything

# DO: Use pipes
process = subprocess.Popen(['cmd'], stdout=subprocess.PIPE)
```

---

## Summary

JN's streaming architecture provides:

| Property | How It's Achieved |
|----------|-------------------|
| **Constant memory** | Pipe buffers (~64KB), no accumulation |
| **Automatic backpressure** | OS blocks writes when pipe full |
| **Early termination** | SIGPIPE propagates when reader exits |
| **True parallelism** | Separate processes, multi-CPU |
| **Simple code** | No async/await, no threading |
| **Robustness** | Process isolation, clean shutdown |

**This is the Unix way—simple, robust, efficient.**

---

## See Also

- [01-vision.md](01-vision.md) - Why this approach
- [02-architecture.md](02-architecture.md) - Pipeline structure
- [05-plugin-system.md](05-plugin-system.md) - Plugin I/O requirements
