# ZQ Prototype

Proof-of-concept implementation validating Zig as the language for JN's native filter.

**Result:** 2-3x faster than jq

## Benchmark Results (100K records)

| Expression | ZQ | jq | Speedup |
|------------|-----|-----|---------|
| `select(.id > 50000)` | 61ms | 196ms | **3.2x** |
| `.value` | 59ms | 131ms | **2.2x** |
| `.` (identity) | 68ms | 191ms | **2.8x** |
| `.meta.score` (nested) | 100ms | 189ms | **1.9x** |
| `select(.meta.active)` | 133ms | 265ms | **2.0x** |

## Current Features

- `.` - identity
- `.field` - single field access
- `.a.b.c` - nested field access
- `select(.field)` - truthy check
- `select(.field > N)` - comparison (>, <, ==, !=)

## Key Optimizations

1. **Arena allocator with reset** - O(1) memory reclaim per line
2. **std.json parsing** - Built-in, no external dependencies
3. **Direct evaluation** - No AST interpretation overhead
4. **Buffered I/O** - Both input and output buffered

## Build & Run

```bash
# Build
zig build -Doptimize=ReleaseFast

# Run
echo '{"x":1}' | ./zig-out/bin/zq '.x'
cat data.ndjson | ./zig-out/bin/zq 'select(.value > 100)'

# Test
zig build test
```

## Binary Size

- ReleaseFast: 2.3MB
- ReleaseSmall: ~500KB

## Next Steps

See [../../ZQ.md](../../ZQ.md) for the full language specification and implementation roadmap.
