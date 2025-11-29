# Experiment: Zig Streaming I/O Benchmark

**Risk:** We claim 10x speedup over Python. Need to validate Zig buffered I/O is actually fast.

**Goal:** Benchmark stdin→stdout line processing in Zig vs Python.

## Test Case

Simple passthrough: read lines from stdin, write to stdout. This isolates I/O performance from parsing.

## Steps

```bash
cd spec/polyglot/experiments/zig-stream-bench

# Build Zig version
zig build -Doptimize=ReleaseFast

# Generate test data (1M lines, ~50MB)
seq 1000000 | while read n; do echo "{\"id\":$n,\"name\":\"test\"}"; done > /tmp/test.ndjson

# Benchmark Python
time python passthrough.py < /tmp/test.ndjson > /dev/null

# Benchmark Zig
time ./zig-out/bin/passthrough < /tmp/test.ndjson > /dev/null

# Benchmark with wc -l baseline
time wc -l < /tmp/test.ndjson
```

## Success Criteria

- [ ] Zig is at least 5x faster than Python
- [ ] Memory usage constant regardless of file size
- [ ] Works with stdin/stdout pipes (not just files)

## Expected Results

| Implementation | Time (1M lines) | Memory |
|---------------|-----------------|--------|
| wc -l (baseline) | ~0.1s | minimal |
| Zig | ~0.2s | ~64KB |
| Python | ~2-3s | ~10MB |

## Files

- `build.zig` - Build configuration
- `src/main.zig` - Zig passthrough
- `passthrough.py` - Python passthrough
