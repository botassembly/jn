# Sprint 04a: Zig 0.15.2 Upgrade

**Status:** Completed
**Sprint Type:** Addendum (infrastructure upgrade)
**Date:** 2025-12

## Executive Summary

Upgrade ZQ from Zig 0.11.0 to Zig 0.15.2 (latest stable). This is a significant upgrade spanning 4 major releases with breaking changes in:

1. **Build system** - `root_source_file` API changed
2. **I/O system ("Writergate")** - Major refactoring of `std.io`
3. **Process API** - `std.ChildProcess` renamed to `std.process.Child`
4. **Language semantics** - Stricter rules, no more `usingnamespace`

## Why 0.15.2?

| Criteria | Recommendation |
|----------|----------------|
| Current stable | 0.15.2 (Oct 2025) |
| Performance | 5x faster debug builds on x86 |
| Future direction | Aligns with I/O evolution and std modernization |
| Package availability | Homebrew, Arch, Guix all ship 0.15.x |
| Ecosystem | Libraries converging on recent releases |

## Scope Analysis

### Files Requiring Changes

| File | Changes Required | Effort |
|------|-----------------|--------|
| `Makefile` | Update ZIG_VERSION to 0.15.2, update URL | Trivial |
| `zq/build.zig` | Update `root_source_file` API | Easy |
| `zq/src/main.zig` | I/O API updates (Writergate) | Medium |
| `zq/tests/integration.zig` | `std.ChildProcess` → `std.process.Child` | Easy |

### What's NOT Affected

The codebase does NOT use:
- `usingnamespace` (removed in 0.15)
- `async`/`await` (removed in 0.15)
- Direct `@export` calls
- Arithmetic with `undefined`
- Lossy int→float coercions

This makes the migration significantly easier.

## Breaking Changes by Version

### 0.11 → 0.12 (Medium)
- Build system changes (mostly handled)
- RLS improvements
- std API churn

### 0.12 → 0.13 (Easy)
- LLVM 18 toolchain
- `std.ChildProcess` → `std.process.Child`
- CRC, StaticStringMap API changes (not used by ZQ)

### 0.13 → 0.14 (Medium)
- Incremental compilation improvements
- Labeled switch (new feature, not breaking)
- Decl literals (new feature)
- Container deprecations

### 0.14 → 0.15 (Hard - primary focus)
- **I/O Refactor (Writergate)**: Old `std.io.Writer`/`Reader` deprecated
- `usingnamespace` removed (not used)
- `async`/`await` removed (not used)
- Stricter undefined/int→float rules

## Implementation Plan

### Phase 1: Build Infrastructure

#### 1.1 Makefile Update
```makefile
# Before
ZIG_VERSION := 0.11.0

# After
ZIG_VERSION := 0.15.2
```

Also update the download URL pattern if needed (same format).

#### 1.2 build.zig Update
```zig
// Before (0.11 syntax)
.root_source_file = .{ .path = "src/main.zig" },

// After (0.15 syntax)
.root_source_file = b.path("src/main.zig"),
```

### Phase 2: I/O Migration (Writergate)

The 0.15 I/O refactor deprecates the old reader/writer interfaces. Current code:

```zig
const stdin = std.io.getStdIn();
const stdout = std.io.getStdOut();
var buf_reader = std.io.bufferedReader(stdin.reader());
var buf_writer = std.io.bufferedWriter(stdout.writer());
const reader = buf_reader.reader();
const writer = buf_writer.writer();
```

Migration options:
1. **Use adapter API** - `adaptToNewApi()` for gradual migration
2. **Direct migration** - Convert to new `std.Io.Reader`/`std.Io.Writer`
3. **Wait and see** - Old APIs still work in 0.15.2, deprecated but functional

**Recommendation:** Start with option 3 (deprecated but working), then migrate as needed. The old APIs still compile in 0.15.2.

### Phase 3: Process API Update

```zig
// Before (0.11-0.12)
var child = std.ChildProcess.init(&args, allocator);

// After (0.13+)
var child = std.process.Child.init(.{
    .argv = &args,
    .allocator = allocator,
});
```

### Phase 4: Testing & Verification

1. Build ZQ with 0.15.2
2. Run unit tests: `zig build test`
3. Run integration tests: `zig build test-integration`
4. Run benchmarks: `make zq-bench`
5. Test jn integration: `make test`

## Task Checklist

- [x] Update Makefile ZIG_VERSION to 0.15.2
- [x] Update zq/build.zig `root_source_file` syntax
- [x] Update zq/tests/integration.zig process API
- [x] Build and fix any remaining compile errors
- [x] Run unit tests (82 passed)
- [x] Run integration tests (25 passed)
- [x] Run full test suite
- [x] Document any behavior differences

## Implementation Notes

### Key Changes Made

1. **Makefile**: Updated ZIG_VERSION and archive URL pattern, switched to `zig build-exe` to work around build system TODO panics with x86 backend.

2. **build.zig**: Changed `root_source_file` from `.{ .path = "..." }` to `b.path("...")`, added `.use_llvm = true`.

3. **main.zig I/O Refactor**:
   - Changed from `std.io.getStdIn()` to `std.fs.File.stdin().reader(&buffer)`
   - Changed from `takeDelimiterExclusive` to `takeDelimiter` (returns null at EOF instead of spinning)
   - Changed `ArrayList` to `ArrayListUnmanaged` with allocator passed to methods

4. **integration.zig Process API**:
   - Changed `Child.init(.{...})` to `Child.init(argv, allocator)`
   - Changed `.pipe` to `.Pipe` (capitalized)
   - Changed `term.code` to switch on `term.Exited` (now a tagged union)
   - Changed `child.wait()` to `try child.wait()` (now returns error union)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| I/O API breakage | Low | Medium | Old APIs still work (deprecated) |
| Build system changes | Medium | Low | Well-documented, straightforward |
| Process API | Low | Low | Simple rename |
| Runtime behavior changes | Low | Low | Comprehensive test suite |

## Success Criteria

1. ZQ builds successfully with Zig 0.15.2
2. All 50+ unit tests pass
3. All integration tests pass
4. Benchmarks show similar or better performance
5. `make test` passes (Python + Zig integration)

## Future Considerations

### 0.16.0 Preparation
- I/O APIs expected to stabilize further
- May want to fully migrate from deprecated I/O APIs
- Track master branch for breaking changes

### Performance Opportunities
- 0.15.2 x86 backend is 5x faster for debug builds
- Could explore incremental compilation
- Arena allocator patterns well-suited to new I/O model

## References

- [Zig 0.15.0 Release Notes](https://ziglang.org/download/0.15.0/release-notes.html)
- [Zig 0.14.0 Release Notes](https://ziglang.org/download/0.14.0/release-notes.html)
- [Zig 0.13.0 Release Notes](https://ziglang.org/download/0.13.0/release-notes.html)
- [Zig 0.12.0 Release Notes](https://ziglang.org/download/0.12.0/release-notes.html)
- [Writergate Discussion](https://github.com/ziglang/zig/issues/17985)
