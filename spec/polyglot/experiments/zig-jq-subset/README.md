# Experiment: Zig jq-subset (zq)

**Goal:** Prototype a minimal jq implementation in Zig for JN's actual needs.

**Result:** ✅ 2-3x faster than jq, 10x faster than jaq-filter

## Supported Expressions

- `.` - identity
- `.field` - single field access
- `.a.b.c` - nested field access
- `select(.field)` - truthy check
- `select(.field > N)` - comparison (>, <, ==, !=)
- `select(.a.b > N)` - nested comparison

## Benchmark Results (100K records)

| Expression | zq (Zig) | jq | jaq-filter | zq vs jq |
|------------|----------|-----|------------|----------|
| `select(.id > 50000)` | 61ms | 196ms | 665ms | **3.2x faster** |
| `.value` | 59ms | 131ms | 596ms | **2.2x faster** |
| `.` (identity) | 68ms | 191ms | - | **2.8x faster** |
| `.meta.score` (nested) | 100ms | 189ms | - | **1.9x faster** |
| `select(.meta.active)` | 133ms | 265ms | - | **2.0x faster** |

## Binary Size

- zq: 2.3MB
- jaq-filter: 5.0MB
- jq: system installed

## Key Implementation Details

1. **Arena allocator with reset** - No per-line allocations, arena resets each iteration
2. **std.json for parsing** - Built-in, no external dependencies
3. **Direct evaluation** - No AST interpretation overhead
4. **Buffered I/O** - Both input and output buffered

## Why So Fast?

1. **No double conversion** - Parse JSON once, evaluate directly
2. **Arena reset vs free** - O(1) memory reclaim per line
3. **Minimal expression parser** - No full jq grammar, just what we need
4. **Static dispatch** - Expression type known at parse time

## Usage

```bash
# Build
zig build -Doptimize=ReleaseFast

# Run
echo '{"x":1}' | ./zig-out/bin/zq '.x'
cat data.ndjson | ./zig-out/bin/zq 'select(.value > 100)'
```

## Limitations

- No pipes (`|`)
- No array operations (`map`, `[]`)
- No arithmetic in expressions
- No `@base64`, `keys`, `length`, etc.

These could be added incrementally if needed.
