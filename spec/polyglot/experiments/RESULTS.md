# Experiment Results

**Date:** 2024-01
**Zig Version:** 0.11.0

## Summary

All three experiments passed, validating the core assumptions of the polyglot architecture.

| Experiment | Status | Key Finding |
|------------|--------|-------------|
| zig-cimport | ✅ PASS | @cImport with PCRE2 works seamlessly |
| zig-stream-bench | ✅ PASS | 35x faster than Python (I/O passthrough) |
| zig-cross-compile | ✅ PASS | All 5 targets build, binaries <100KB |
| rust-jaq | ✅ PASS | jaq library works, eliminates jq dependency |
| zig-jq-subset | ✅ PASS | **2-3x faster than jq**, 10x faster than jaq |

---

## 1. zig-cimport (PCRE2 Integration)

**Goal:** Validate C library integration via @cImport

**Result:** ✅ PASS

- PCRE2 headers import cleanly
- Regex compilation and matching work correctly
- Tests pass: `zig build test`
- No memory leaks detected

**Example output:**
```
$ echo -e "test.csv\ntest.json" | ./regex-test '.*\.csv$'
match: test.csv
no match: test.json
```

**Notes:**
- Required `libpcre2-dev` system package
- Zig 0.11.0 uses `.{ .path = "..." }` for source files (not `b.path()`)

---

## 2. zig-stream-bench (I/O Performance)

**Goal:** Validate performance claims (10x faster than Python)

**Result:** ✅ PASS (35x faster)

**Benchmark:** 500K lines NDJSON passthrough (11MB)

| Implementation | Time | Speedup |
|---------------|------|---------|
| wc -l (baseline) | 0.018s | - |
| Zig (ReleaseFast) | 0.067s | 35x |
| Zig (ReleaseSmall) | 0.180s | 13x |
| Python | 2.391s | 1x |

**Binary sizes:**
| Optimization | Size |
|--------------|------|
| ReleaseFast | 1.7MB |
| ReleaseSmall | 17KB |

**Notes:**
- ReleaseFast is 35x faster than Python
- ReleaseSmall trades speed for size (still 13x faster)
- For plugins, ReleaseFast recommended (size is less critical)

---

## 3. zig-cross-compile (Multi-Platform)

**Goal:** Validate cross-compilation for all target platforms

**Result:** ✅ PASS

**Built artifacts (ReleaseSmall):**

| Target | Size | Format |
|--------|------|--------|
| linux-x86_64 | 8.7KB | ELF 64-bit, statically linked |
| linux-aarch64 | 8.7KB | ELF 64-bit ARM, statically linked |
| macos-x86_64 | 23KB | Mach-O 64-bit |
| macos-aarch64 | 52KB | Mach-O 64-bit ARM |
| windows-x86_64 | 4.5KB | PE32+ |

**Notes:**
- All targets build from single Linux machine
- No external toolchains needed
- Linux binaries are statically linked (no libc dependency)
- macOS binaries are larger due to Mach-O format

---

## 4. rust-jaq (jq Replacement)

**Goal:** Validate jaq library for NDJSON filtering, compare to jq

**Result:** ✅ PASS (functional, with caveats)

**Benchmark:** 100K NDJSON records

| Implementation | select(.id > 50000) | .value | Startup |
|---------------|---------------------|--------|---------|
| jaq-filter (Rust) | 408ms | 561ms | 16ms |
| jq | 181ms | 130ms | 20ms |
| Python + jq | 238ms | N/A | 87ms |

**Observations:**
- jq is 2-4x faster for throughput than our naive jaq implementation
- Startup times are similar (jq ~20ms, jaq ~16ms)
- Python adds ~70ms overhead per invocation
- Binary size: 5.0MB (at target)

**Why still use jaq?**

1. **No external dependency** - jq must be installed separately
2. **Bundled distribution** - Single binary includes filter capability
3. **Cross-platform** - Same binary works everywhere
4. **API compatibility** - Supports JN's usage patterns (select, field access)

**Performance Note:**
Our implementation uses serde_json for parsing/serialization. jaq docs recommend `hifijson` for better performance. A production implementation should:
- Use `hifijson` instead of serde_json
- Avoid Val↔JSON conversions where possible
- Consider streaming JSON parsing

**Compatibility Tested:**
- [x] Field access: `.name`, `.nested.field`
- [x] Select: `select(.active)`, `select(.id > N)`
- [x] Identity: `.`

---

## 5. zig-jq-subset (zq)

**Goal:** Prototype minimal jq in Zig for JN's actual filter needs

**Result:** ✅ PASS (2-3x faster than jq!)

**Benchmark:** 100K NDJSON records

| Expression | zq (Zig) | jq | jaq-filter | zq vs jq |
|------------|----------|-----|------------|----------|
| `select(.id > 50000)` | 61ms | 196ms | 665ms | **3.2x faster** |
| `.value` | 59ms | 131ms | 596ms | **2.2x faster** |
| `.` (identity) | 68ms | 191ms | - | **2.8x faster** |
| `.meta.score` | 100ms | 189ms | - | **1.9x faster** |
| `select(.meta.active)` | 133ms | 265ms | - | **2.0x faster** |

**Binary size:** 2.3MB (vs jaq's 5.0MB)

**Key optimizations:**
1. **Arena allocator with reset** - No per-line allocations
2. **Direct evaluation** - No AST interpretation
3. **Buffered I/O** - Both input and output
4. **Single parse** - No JSON→Val→JSON conversions

**Supported expressions:**
- `.field`, `.a.b.c` (field access)
- `select(.x)`, `select(.x > N)`, `select(.x == "str")` (filtering)
- `.` (identity)

**Initial bug:** Used GeneralPurposeAllocator which is debug-oriented. First run was 47s (267x slower than jq!). Switching to ArenaAllocator with per-line reset fixed it.

**Conclusion:** A minimal Zig jq implementation can beat jq at its own game. For JN's filter needs, this is the fastest option.

---

## Issues Found & Fixed

### 1. Zig 0.11.0 API Changes

**Problem:** Build files used `b.path()` which doesn't exist in 0.11.0

**Fix:** Use `.{ .path = "src/main.zig" }` instead

```zig
// Wrong (Zig 0.12+)
.root_source_file = b.path("src/main.zig"),

// Correct (Zig 0.11.0)
.root_source_file = .{ .path = "src/main.zig" },
```

### 2. std.Target.current Removed

**Problem:** `std.Target.current` was removed in 0.11.0

**Fix:** Use `@import("builtin")`

```zig
// Wrong
@tagName(std.Target.current.cpu.arch)

// Correct
const builtin = @import("builtin");
@tagName(builtin.cpu.arch)
```

### 3. jaq API Changes (v1.5)

**Problem:** jaq-core/jaq-std v2 doesn't exist, v1.5 has different API

**Fix:** Use jaq-interpret v1.5 with ParseCtx

```rust
// Build with ParseCtx instead of Definitions
let mut defs = ParseCtx::new(Vec::new());
defs.insert_natives(jaq_core::core());
defs.insert_defs(jaq_std::std());
let filter = defs.compile(filter);
```

---

## Conclusions

1. **C interop works** - @cImport with PCRE2 is seamless. simdjson, libcurl should work similarly.

2. **Zig performance validated** - 35x faster I/O than Python exceeds our 10x target.

3. **Cross-compilation works** - Single command builds for all platforms, no toolchain setup.

4. **Binary sizes are excellent** - 8-50KB for Zig binaries, 2.3MB for Zig jq-subset, 5MB for Rust jaq.

5. **Zig jq-subset beats jq** - 2-3x faster than jq itself! Arena allocator + direct evaluation + buffered I/O is the winning combination.

6. **jaq works but is slower** - Functional jq replacement, but naive implementation is 2-4x slower than jq due to serde_json conversions. Could optimize with hifijson, but Zig approach is better.

**Recommendation:** Proceed with Sprint 01. All core assumptions validated:
- Zig for core and hot-path plugins ✅
- **Zig for jq replacement** ✅ (faster than jq, no dependency)
- Cross-platform distribution ✅

**Updated plan:** Consider Zig jq-subset instead of Rust/jaq for filter plugin. Simpler, faster, smaller binary.
