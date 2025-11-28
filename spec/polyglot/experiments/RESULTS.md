# Experiment Results

**Date:** 2024-01
**Zig Version:** 0.11.0

## Summary

All experiments passed, validating the core assumptions of the polyglot architecture.

| Experiment | Status | Key Finding |
|------------|--------|-------------|
| zig-cimport | PASS | @cImport with PCRE2 works seamlessly |
| zig-stream-bench | PASS | 35x faster than Python (I/O passthrough) |
| zig-cross-compile | PASS | All 5 targets build, binaries <100KB |
| zig-jq-subset | PASS | **2-3x faster than jq** for core operations |

---

## 1. zig-cimport (PCRE2 Integration)

**Goal:** Validate C library integration via @cImport

**Result:** PASS

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

**Implications:** Can integrate simdjson, libcurl, or any C library for hot paths.

---

## 2. zig-stream-bench (I/O Performance)

**Goal:** Validate performance claims (10x faster than Python)

**Result:** PASS (35x faster)

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

**Implications:** Zig plugins will dramatically outperform Python for I/O-bound operations.

---

## 3. zig-cross-compile (Multi-Platform)

**Goal:** Validate cross-compilation for all target platforms

**Result:** PASS

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

**Implications:** Single CI pipeline can produce all platform binaries.

---

## 4. zig-jq-subset (ZQ)

**Goal:** Prototype minimal jq in Zig for JN's actual filter needs

**Result:** PASS (2-3x faster than jq!)

**Benchmark:** 100K NDJSON records

| Expression | ZQ (Zig) | jq | ZQ vs jq |
|------------|----------|-----|----------|
| `select(.id > 50000)` | 61ms | 196ms | **3.2x faster** |
| `.value` | 59ms | 131ms | **2.2x faster** |
| `.` (identity) | 68ms | 191ms | **2.8x faster** |
| `.meta.score` | 100ms | 189ms | **1.9x faster** |
| `select(.meta.active)` | 133ms | 265ms | **2.0x faster** |

**Binary size:** 2.3MB

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

**Implications:** ZQ will be JN's native filter language, replacing jq dependency.

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

### 3. GeneralPurposeAllocator Performance

**Problem:** GPA is debug-oriented, 267x slower than expected

**Fix:** Use ArenaAllocator with `.reset(.retain_capacity)` per line

```zig
var arena = std.heap.ArenaAllocator.init(page_alloc);
while (readLine()) |line| {
    _ = arena.reset(.retain_capacity);  // O(1) memory reclaim
    // ... process line
}
```

---

## Conclusions

1. **C interop works** - @cImport with PCRE2 is seamless. simdjson, libcurl should work similarly.

2. **Zig performance validated** - 35x faster I/O than Python exceeds our 10x target.

3. **Cross-compilation works** - Single command builds for all platforms, no toolchain setup.

4. **Binary sizes are excellent** - 8-50KB for simple binaries, 2.3MB for ZQ with JSON parsing.

5. **ZQ beats jq** - 2-3x faster than jq itself! Arena allocator + direct evaluation + buffered I/O is the winning combination.

**Recommendation:** Proceed with Zig implementation. All core assumptions validated:
- Zig for core and hot-path plugins
- Zig for ZQ (filter language)
- Cross-platform distribution
