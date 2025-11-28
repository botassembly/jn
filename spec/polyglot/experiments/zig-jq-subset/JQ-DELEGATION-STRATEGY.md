# JQ Delegation Strategy: zq (Native) vs zq-wrap (Wrapper)

**Goal:** Implement 20% of jq features natively in Zig for 2-3x performance gains, delegate 80% to jq wrapper for full compatibility.

## Executive Summary

| Metric | zq (Native) | zq-wrap (Wrapper) |
|--------|-------------|-------------------|
| Performance | 2-3x faster than jq | ~10% faster than jq |
| Compatibility | ~20% of jq features | 100% of jq features |
| Binary size | 2.3MB | 1.8MB |
| Dependencies | None | Requires jq installed |
| Startup | ~5ms | ~20ms |

**Recommendation:** Hybrid approach - detect expression complexity, route simple expressions to native zq, complex ones to zq-wrap.

---

## JQ Feature Inventory (218 Builtins)

### Category 1: NATIVE ZQ - High Value, Low Effort (Implement in Zig)

These features cover ~90% of JN's actual usage based on codebase analysis:

#### 1.1 Identity & Field Access (DONE)
| Feature | Example | Effort | JN Usage |
|---------|---------|--------|----------|
| `.` | identity | Done | Very High |
| `.field` | `.name` | Done | Very High |
| `.a.b.c` | `.meta.score` | Done | High |
| `.[n]` | `.[0]` | 2 hrs | Medium |
| `.[]` | iterate array | 4 hrs | High |

#### 1.2 Selection/Filtering (DONE)
| Feature | Example | Effort | JN Usage |
|---------|---------|--------|----------|
| `select(cond)` | `select(.x > 10)` | Done | Very High |
| `select(.x == "str")` | equality | Done | Very High |
| `select(.x != val)` | inequality | Done | High |
| `select(.x)` | truthy check | Done | High |

#### 1.3 Type Conversion (HIGH PRIORITY)
| Feature | Example | Effort | JN Usage |
|---------|---------|--------|----------|
| `tostring` | `.id \| tostring` | 2 hrs | High |
| `tonumber` | `.revenue \| tonumber` | 2 hrs | High |
| `type` | `.x \| type` | 1 hr | Medium |

#### 1.4 Comparison (PARTIAL)
| Feature | Example | Effort | JN Usage |
|---------|---------|--------|----------|
| `>`, `<`, `>=`, `<=` | numeric | Done | High |
| `==`, `!=` | equality | Done | High |
| `and`, `or`, `not` | boolean logic | 2 hrs | Medium |

#### 1.5 Object Construction (HIGH PRIORITY)
| Feature | Example | Effort | JN Usage |
|---------|---------|--------|----------|
| `{a: .x, b: .y}` | object literal | 8 hrs | Very High |
| `{(.key): .value}` | dynamic keys | 4 hrs | Medium |

**Native zq Total: ~25 hours to implement core features**

---

### Category 2: WRAPPER - Medium Value, High Effort

These features are used in jq profiles but too complex for native implementation:

#### 2.1 Array Operations
| Feature | Example | Effort | JN Usage |
|---------|---------|--------|----------|
| `map(f)` | `map(.x + 1)` | 16 hrs | High (profiles) |
| `select` inside map | `map(select(...))` | 8 hrs | Medium |
| `add` | `[1,2,3] \| add` | 4 hrs | High (profiles) |
| `flatten` | nested → flat | 8 hrs | Low |
| `unique` | deduplicate | 4 hrs | Medium |
| `reverse` | reverse array | 2 hrs | Low |
| `sort`, `sort_by` | sorting | 8 hrs | Medium |
| `group_by` | grouping | 16 hrs | High (profiles) |
| `min`, `max`, `min_by`, `max_by` | aggregation | 8 hrs | Medium |
| `first`, `last`, `nth` | element access | 4 hrs | Low |
| `length` | array/string length | 2 hrs | High |
| `contains`, `inside` | containment | 8 hrs | Low |

#### 2.2 Object Operations
| Feature | Example | Effort | JN Usage |
|---------|---------|--------|----------|
| `keys`, `keys_unsorted` | get keys | 4 hrs | Medium |
| `values` | get values | 2 hrs | Low |
| `has(key)` | key exists | 2 hrs | Medium |
| `in(obj)` | value in object | 2 hrs | Low |
| `to_entries`, `from_entries` | obj ↔ array | 8 hrs | High (profiles) |
| `with_entries` | transform entries | 8 hrs | Medium |
| `del(.key)` | delete key | 4 hrs | Low |
| `getpath`, `setpath` | path operations | 8 hrs | Low |

#### 2.3 String Operations
| Feature | Example | Effort | JN Usage |
|---------|---------|--------|----------|
| `split(sep)` | string → array | 4 hrs | Medium |
| `join(sep)` | array → string | 4 hrs | High (profiles) |
| `test(regex)` | regex match | 16 hrs | Medium |
| `match(regex)` | regex capture | 24 hrs | Low |
| `sub`, `gsub` | regex replace | 24 hrs | Low |
| `startswith`, `endswith` | prefix/suffix | 4 hrs | Medium |
| `ltrimstr`, `rtrimstr` | trim | 4 hrs | Low |
| `ascii_downcase`, `ascii_upcase` | case | 2 hrs | Low |
| `explode`, `implode` | char codes | 4 hrs | Low |

#### 2.4 Control Flow
| Feature | Example | Effort | JN Usage |
|---------|---------|--------|----------|
| `if-then-else` | conditionals | 8 hrs | High (profiles) |
| `//` | alternative | 4 hrs | Very High (profiles) |
| `try-catch` | error handling | 8 hrs | Low |
| `empty` | no output | 2 hrs | Low |
| `error` | raise error | 2 hrs | Low |
| `recurse` | recursive descent | 16 hrs | Low |

#### 2.5 Arithmetic
| Feature | Example | Effort | JN Usage |
|---------|---------|--------|----------|
| `+`, `-`, `*`, `/`, `%` | basic math | 4 hrs | Medium |
| `floor`, `ceil`, `round` | rounding | 2 hrs | Low |
| `sqrt`, `pow` | advanced math | 2 hrs | Low |
| All trig functions | sin, cos, etc | 4 hrs | Very Low |

#### 2.6 Input/Output
| Feature | Example | Effort | JN Usage |
|---------|---------|--------|----------|
| `inputs` | slurp remaining | 8 hrs | High (profiles) |
| `input` | read one | 4 hrs | Low |
| `debug` | debug output | 2 hrs | Low |
| `@base64`, `@base64d` | encoding | 8 hrs | Low |
| `@uri`, `@csv`, `@json` | format | 8 hrs | Low |
| `tojson`, `fromjson` | JSON encode/decode | 4 hrs | Low |

#### 2.7 Date/Time
| Feature | Example | Effort | JN Usage |
|---------|---------|--------|----------|
| `now` | current time | 2 hrs | Low |
| `strftime`, `strptime` | format/parse | 16 hrs | Low |
| `gmtime`, `localtime` | time conversion | 8 hrs | Low |

---

### Category 3: NEVER IMPLEMENT - Very Low Value

| Feature | Reason |
|---------|--------|
| `$ENV`, `env` | Environment vars - wrapper sufficient |
| `@text`, `@sh` | Shell formatting - use shell |
| `modulemeta`, `import` | Module system - overkill |
| `builtins` | Meta-introspection - not needed |
| `path`, `getpath`, `delpaths` | Complex path ops - rare |
| `walk` | Recursive transform - use wrapper |
| `limit`, `until`, `while`, `repeat` | Iteration - use wrapper |
| SQL operators (IN, INDEX, JOIN) | Too specialized |
| Bessel functions (j0, j1, jn, y0, y1, yn) | Scientific - wrapper |
| Advanced math (gamma, erf, etc.) | Scientific - wrapper |

---

## JN Actual Usage Analysis

### From test_filter.py:
```python
# High frequency
".name"                    # Field access
"select(.age > 25)"        # Numeric comparison
```

### From filtering.py (auto-generated filters):
```python
# High frequency
"select((.revenue | tonumber) > 1000)"  # Numeric with tonumber
"select((.category | tostring) == \"Electronics\")"  # String equality
```

### From jq profiles (advanced):
```jq
# group_sum.jq - Aggregation
group_by(.[$by]) | map({...}) | add

# pivot.jq - Pivot table
group_by(.[$row_key]) | map(...) | from_entries

# extract-alterations.jq - Object construction
{gene: .gene, name: .name, position: (.p_start // .position // null)}
```

### Usage Frequency Summary:

| Feature | Frequency | Native? |
|---------|-----------|---------|
| `.field` access | Very High | Yes |
| `select(.x > N)` | Very High | Yes |
| `select(.x == "str")` | Very High | Yes |
| `{a: .x, b: .y}` object construction | High | Priority |
| `//` alternative/default | High | Priority |
| `if-then-else` | Medium | Wrapper |
| `group_by`, `map` | Medium (profiles) | Wrapper |
| `tonumber`, `tostring` | Medium | Priority |
| `inputs` (slurp) | Low (profiles) | Wrapper |
| Everything else | Low | Wrapper |

---

## Delegation Strategy

### Detection Algorithm

```zig
fn shouldUseNative(expr: []const u8) bool {
    // Native-supported patterns (regex-like matching)
    const native_patterns = [_][]const u8{
        "^\\.$",                           // Identity
        "^\\.[a-zA-Z_][a-zA-Z0-9_]*$",    // Single field
        "^\\.[a-zA-Z_][a-zA-Z0-9_.]*$",   // Field path
        "^select\\(\\.[^|]+[><=!]+.+\\)$", // Simple select
    };

    // Wrapper-required patterns
    const wrapper_patterns = [_][]const u8{
        "\\|",        // Pipes
        "map\\(",     // Map
        "group_by",   // Grouping
        "inputs",     // Slurp
        "\\[.*\\]",   // Array operations
        "if.*then",   // Conditionals
        "@",          // Format strings
    };

    // Check wrapper patterns first (conservative)
    for (wrapper_patterns) |pat| {
        if (matches(expr, pat)) return false;
    }

    // Check native patterns
    for (native_patterns) |pat| {
        if (matches(expr, pat)) return true;
    }

    // Default to wrapper for unknown
    return false;
}
```

### Hybrid Binary Architecture

```
zq (entry point)
├── Parse expression
├── Detect complexity
├── Route:
│   ├── Native path (simple expressions)
│   │   └── Arena allocator, buffered I/O, 2-3x faster
│   └── Wrapper path (complex expressions)
│       └── exec("jq", "-c", expr) with inherited I/O
```

### Implementation Priority

**Phase 1: Core Native (Week 1)**
- [x] Identity (.)
- [x] Field access (.field, .a.b.c)
- [x] Select with comparisons (select(.x > N))
- [ ] Boolean logic (and, or, not)
- [ ] Array index (.[0], .[-1])

**Phase 2: Extended Native (Week 2)**
- [ ] Object construction ({a: .x, b: .y})
- [ ] tonumber, tostring, type
- [ ] length (arrays and strings)
- [ ] Array iteration (.[] )
- [ ] Alternative operator (//)

**Phase 3: Delegation (Week 3)**
- [ ] Expression complexity detection
- [ ] Seamless wrapper fallback
- [ ] Test coverage for routing decisions

**Phase 4: Optimization (Week 4)**
- [ ] Benchmark suite
- [ ] Hot path profiling
- [ ] SIMD JSON parsing (optional)

---

## Binary Distribution Strategy

### Option A: Dual Binary (Recommended)
```
jn_home/plugins/filters/
├── zq       # Native Zig, 2.3MB
└── zq-wrap  # Wrapper, 1.8MB (fallback)
```

JN detects which to use based on expression complexity.

### Option B: Single Hybrid Binary
```
jn_home/plugins/filters/
└── zq  # Contains both native + wrapper logic
```

Single binary, internally routes.

### Option C: Native Only + System jq
```
jn_home/plugins/filters/
└── zq  # Native only, fails gracefully to system jq
```

Simplest, relies on jq being installed.

**Recommendation:** Option B - Single hybrid binary provides best UX with automatic optimization.

---

## Performance Expectations

| Expression Type | zq Native | zq-wrap | jq Direct |
|-----------------|-----------|---------|-----------|
| `.field` | 59ms | 193ms | 216ms |
| `select(.x > N)` | 61ms | 196ms | 196ms |
| `{a: .x, b: .y}` | ~80ms (est) | 200ms | 200ms |
| `group_by \| map` | N/A | 220ms | 220ms |
| Complex pipeline | N/A | 250ms | 250ms |

**Estimated Coverage:**
- 60-70% of JN filter invocations → Native (2-3x faster)
- 30-40% of JN filter invocations → Wrapper (same speed)
- Net improvement: ~40-50% faster average filter performance

---

## Testing Strategy

### Unit Tests
```zig
test "native: identity" { ... }
test "native: field access" { ... }
test "native: select gt" { ... }
test "routing: simple goes native" { ... }
test "routing: complex goes wrapper" { ... }
```

### Integration Tests
```bash
# Native path
echo '{"x":1}' | zq '.x'
echo '{"x":1}' | zq 'select(.x > 0)'

# Wrapper path (auto-detected)
echo '{"x":1}' | zq '.x | tostring'
echo '[1,2,3]' | zq 'map(. * 2)'

# Explicit wrapper
echo '{"x":1}' | zq --wrapper '.x'
```

### Benchmark Suite
```bash
# Compare native vs wrapper vs jq
./benchmark.sh ".value" 100000
./benchmark.sh "select(.id > 50000)" 100000
./benchmark.sh "{x: .value}" 100000
./benchmark.sh "group_by(.type)" 100000
```

---

## Conclusion

The 80/20 strategy is achievable:

1. **20% of jq features** (identity, field access, select, object construction, type conversion) cover **~70% of JN's actual usage**

2. **Native implementation** provides **2-3x speedup** for hot path operations

3. **Wrapper fallback** ensures **100% compatibility** with no user-visible degradation

4. **~25-40 hours** of implementation work for Phase 1-2, with measurable performance wins

5. **Risk mitigation**: If native path has bugs, wrapper is always available as fallback

**Next Steps:**
1. Implement object construction `{a: .x}` in native zq
2. Add expression complexity detection
3. Integrate wrapper fallback
4. Benchmark and iterate
