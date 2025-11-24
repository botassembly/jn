# Textual TUI Integration with JN Pipelines

## Core JN Principles (Never Compromise These)

1. **Constant Memory Usage** - Process 10GB files with ~1MB RAM
2. **Automatic Backpressure** - OS pipes handle flow control
3. **Streaming by Default** - First output immediately, not after loading all data
4. **Early Termination** - `| head -n 10` stops upstream after 10 records

**Critical**: Any TUI solution MUST preserve these principles. Loading all data into RAM is acceptable ONLY for small datasets where memory usage is negligible (< 10K records as a guideline).

---

## The Fundamental Problem

### What We Need
- **Data from stdin**: `jn cat data.csv | jn view` (piped NDJSON stream)
- **Keyboard from terminal**: User presses `n`, `p`, `q` for navigation

### The Conflict
Both try to read from the same source (stdin, file descriptor 0):
- When stdin is piped with data, Textual can't read keyboard input
- When Textual takes over stdin for keyboard, the data stream is lost

### How Textual Reads Input
```python
# Textual's LinuxDriver directly accesses file descriptor 0
sys.__stdin__.fileno()  # Always reads from fd 0
```

**Key insight**: Textual uses `sys.__stdin__` (original reference), not `sys.stdin` (which can be reassigned).

---

## Solution Strategies (Ranked by JN Philosophy Alignment)

### ✅ Option 1: Disk-Backed Streaming (RECOMMENDED)

**Approach**: Save stdin to temp file, then stream from disk

```python
if not sys.stdin.isatty():
    # 1. Save piped data to temp file (one-pass write)
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ndjson') as f:
        temp_path = f.name
        for line in sys.stdin:
            f.write(line)  # Streaming write

    # 2. Redirect stdin to /dev/tty for keyboard
    tty_fd = os.open('/dev/tty', os.O_RDONLY)
    os.dup2(tty_fd, 0)
    os.close(tty_fd)
    sys.stdin = open(0, 'r')

    # 3. Stream from temp file (constant memory)
    def load_from_file():
        with open(temp_path) as f:
            for line in f:
                yield json.loads(line.strip())

    app = JSONViewerApp(data_source=load_from_file)
    app.run()
    os.unlink(temp_path)  # Cleanup
```

**Pros:**
- ✅ Constant memory (stream from disk)
- ✅ Can seek forward/back efficiently
- ✅ Works on all platforms (Linux, macOS, Ghostty, tmux)
- ✅ Simple, reliable

**Cons:**
- Requires disk I/O (but so does the source data usually)
- Temp file overhead (negligible for most cases)

**Memory usage**: ~1MB regardless of dataset size
**Disk usage**: Same as input size (NDJSON is compressed)

---

### ⚠️ Option 2: Chunked Loading (For Very Large Datasets)

**Approach**: Load records in chunks as user navigates

```python
class ChunkedNavigator:
    def __init__(self, file_path, chunk_size=1000):
        self.file_path = file_path
        self.chunk_size = chunk_size
        self.chunks = {}  # {chunk_id: [records]}
        self.current_chunk = 0
        self.current_index = 0

    def get_record(self, index):
        chunk_id = index // self.chunk_size
        if chunk_id not in self.chunks:
            self._load_chunk(chunk_id)
        offset = index % self.chunk_size
        return self.chunks[chunk_id][offset]

    def _load_chunk(self, chunk_id):
        # Seek to chunk position, load only that chunk
        start = chunk_id * self.chunk_size
        with open(self.file_path) as f:
            for i, line in enumerate(f):
                if i < start:
                    continue
                if i >= start + self.chunk_size:
                    break
                # Load chunk...
```

**Pros:**
- ✅ Lower memory than full pre-load
- ✅ Faster startup (only load first chunk)
- ✅ Can handle very large files

**Cons:**
- More complexity
- Seeking can be slow for line-based formats
- Need to track chunk boundaries

**Use when**: > 100K records, or user explicitly requests chunking

---

### ❌ Option 3: Full Pre-load (AVOID Unless Necessary)

**Approach**: Load all records into memory before starting TUI

```python
records = [json.loads(line) for line in sys.stdin]  # Loads everything!
# Redirect stdin...
app = JSONViewerApp(records=records)
app.run()
```

**Pros:**
- Simple code
- Fast navigation

**Cons:**
- ❌ Violates JN's constant memory principle
- ❌ Can't handle large datasets (OOM errors)
- ❌ Slow startup for big files
- ❌ No backpressure (loads everything immediately)

**Only acceptable when**: Dataset is tiny (< 10K records) and user explicitly pipes to viewer

---

## Platform-Specific Considerations

| Platform | Auto-Opens /dev/tty? | Requires os.dup2()? | Notes |
|----------|---------------------|---------------------|-------|
| Linux | ✅ Usually | ⚠️ Recommended | May work without but safer with |
| macOS | ❌ No | ✅ Required | Especially Ghostty terminal |
| tmux/screen | ✅ Yes | ⚠️ Recommended | - |
| SSH | ✅ Yes | ⚠️ Recommended | - |

**Recommendation**: Always use `os.dup2()` for maximum compatibility

---

## Common Issues & Debugging

### "I/O operation on closed file"
**Cause**: Closed stdin before starting Textual
**Fix**: Use `os.dup2()` to redirect fd 0, never close it

### Keyboard doesn't work (no response to keys)
**Cause**: stdin still reading from pipe, not terminal
**Fix**: Redirect stdin to /dev/tty using `os.dup2()`

### Random escape sequences printed
**Cause**: Terminal control codes read as data instead of being interpreted
**Fix**: stdin not properly redirected to /dev/tty yet

### Works on Linux, breaks on macOS
**Cause**: Linux Textual driver auto-opens /dev/tty, macOS doesn't
**Fix**: Explicitly redirect on all platforms

### Viewer hangs / "Loading..." forever
**Cause**: Reading stdin in background while TUI also tries to access it
**Fix**: Use disk-backed streaming (Option 1)

---

## Implementation Pattern for JN

### For `jn view <file>` (Direct File Access)
```python
# Already works great! Stream directly from disk
with open(file_path) as f:
    for line in f:
        yield json.loads(line)
```
**Memory**: Constant (~1MB)
**Performance**: Excellent

### For `jn cat X | jn view` (Piped Input)
```python
if not sys.stdin.isatty():
    # 1. Save to temp file (streaming write)
    temp_file = save_stdin_to_temp()

    # 2. Redirect stdin to /dev/tty
    redirect_stdin_to_tty()

    # 3. Stream from temp file
    app = JSONViewerApp(data_source=temp_file)
    app.run()

    # 4. Cleanup
    os.unlink(temp_file)
```
**Memory**: Constant (~1MB)
**Disk**: Same as input size

---

## Textual Components We Use

### Key Classes
- `App` - Main application container, handles event loop
- `Screen` - Full-screen container (we use for modals)
- `Widget` - Base for all UI components
- `Tree` - Hierarchical data display (JSON structure)
- `Input` - Text input for dialogs
- `Static` - Static text display
- `Footer` - Status bar at bottom
- `Header` - Title bar at top

### Event Handling
```python
# Action bindings (keyboard shortcuts)
Binding("n", "next_record", "Next")
def action_next_record(self):
    # Handle 'n' key
    pass

# Modal dialogs
def action_search(self):
    self.push_screen(SearchDialog(), callback)
```

### Common Patterns
```python
# Update display from background thread
self.call_from_thread(self.update_ui)

# Show temporary status message
self.sub_title = "Record copied!"
self.set_timer(2.0, lambda: setattr(self, 'sub_title', ''))
```

---

## Testing TUI Apps

### Manual Testing Pattern
```bash
# 1. Create tmux session
tmux new-session -d -s test

# 2. Send command
tmux send-keys -t test "jn view test.csv" Enter

# 3. Capture screen after delay
sleep 2
tmux capture-pane -t test -p

# 4. Send keystrokes
tmux send-keys -t test "n"  # Next record

# 5. Cleanup
tmux kill-session -t test
```

### Debug Logging
```python
# Write to separate file (not stdout/stderr which TUI uses)
with open('/tmp/debug.log', 'a') as f:
    f.write(f"DEBUG: {message}\n")
```

---

## Decision Matrix: When to Use Which Approach

| Scenario | Recommended Approach | Memory | Startup | Seeking |
|----------|---------------------|--------|---------|---------|
| < 10K records, piped | Option 3 (pre-load) | ~2x JSON | Instant | Instant |
| < 100K records, piped | Option 1 (disk-backed) | ~1MB | Fast | Fast |
| > 100K records, piped | Option 1 + chunking | ~1MB | Fast | Medium |
| Direct file | Stream from file | ~1MB | Instant | Fast |
| Infinite stream | Not supported (must materialize to disk first) | - | - | - |

---

## Key Takeaways

1. **Never sacrifice JN's streaming principles for TUI convenience**
2. **Disk-backed streaming is the sweet spot** - constant memory, fast enough
3. **Always redirect stdin to /dev/tty** using `os.dup2()` for keyboard input
4. **Pre-loading is acceptable ONLY for tiny datasets** (< 10K records)
5. **Test on multiple platforms** (Linux, macOS, tmux) before shipping

---

## References

- Textual Documentation: https://textual.textualize.io/
- Unix File Descriptors: `man dup2`
- JN Architecture: `spec/done/arch-backpressure.md`
