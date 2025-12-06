# Zig Code Review Report

**Date:** December 6, 2025
**Reviewer:** Claude Code (Opus 4)
**Codebase:** JN - Universal Data Pipeline Tool
**Files Reviewed:** ~17,000 lines of Zig code across libs, tools, and plugins

---

## Executive Summary

This review identified **23 issues** across the Zig codebase, ranging from critical security vulnerabilities to minor code quality concerns. The codebase demonstrates generally solid Zig practices with good use of arena allocators and proper error handling in most places. However, several issues warrant attention before production deployment.

---

## Critical Issues (3)

### 1. Shell Command Injection via Unescaped URLs
**Location:** `tools/zig/jn-cat/main.zig:1047-1070`
**Severity:** Critical

When `address.raw` contains shell metacharacters (e.g., in URL query parameters), they are passed unescaped to the shell command.

```zig
const curl_cmd = try std.fmt.allocPrint(
    allocator,
    "curl -fsSL {s}",  // address.raw not escaped
    .{address.raw},
);
const argv = [_][]const u8{ "/bin/sh", "-c", curl_cmd };
```

**Risk:** Remote command injection if URLs contain `$(...)`, backticks, or other shell metacharacters.

**Fix:** Use `shell.singleQuoteEscape()` on `address.raw` before interpolation.

---

### 2. Global Mutable State Race Condition
**Location:** `tools/zig/jn-sh/main.zig:26-27`

```zig
var global_args_buffer: [1024][]const u8 = undefined;
var global_args_count: usize = 0;
```

These global variables are modified during parsing and read during command execution. In a multi-threaded context (or signal handler), this creates undefined behavior.

**Fix:** Pass argument buffer as a parameter to parsing functions, or use thread-local storage.

---

### 3. Integer Overflow in fabs Builtin
**Location:** `zq/src/main.zig:2220-2221`

```zig
.fabs => {
    switch (value) {
        .integer => |i| {
            const abs_val = if (i < 0) -i else i;  // Overflow when i == minInt(i64)
```

For `i64.min` (-9223372036854775808), negation overflows because i64.max is 9223372036854775807.

**Fix:** Use `std.math.absCast` or handle the edge case explicitly.

---

## High Priority Issues (8)

### 4. Memory Leak in Profile Loading
**Location:** `libs/zig/jn-profile/src/profile.zig:296-309`

```zig
fn loadFromFile(allocator: Allocator, path: []const u8) !?Profile {
    const file = std.fs.openFileAbsolute(path, .{}) catch |err| {
        // ...
    };
    defer file.close();

    const content = file.readToEndAlloc(allocator, max_file_size) catch return null;
    // No free of content on subsequent errors
```

If `parseYamlProfile` fails after `content` is allocated, the memory leaks.

**Fix:** Add `errdefer allocator.free(content);` after the allocation.

---

### 5. Integer Overflow in Shell Buffer Size
**Location:** `libs/zig/jn-core/src/shell.zig:28`

```zig
pub fn singleQuoteEscape(allocator: Allocator, input: []const u8) ![]const u8 {
    const worst_case = 2 + input.len * 4;  // Can overflow for large inputs
```

For inputs larger than ~4GB, `input.len * 4` overflows.

**Fix:** Use `std.math.mul(usize, input.len, 4) catch return error.Overflow`.

---

### 6. Fixed Buffer Overflow in jn-sh
**Location:** `tools/zig/jn-sh/main.zig:170-171`

```zig
var global_args_buffer: [1024][]const u8 = undefined;
// ... later ...
if (global_args_count >= global_args_buffer.len) {
    // No error - just silently truncates!
}
```

Commands with more than 1024 arguments are silently truncated without error.

**Fix:** Return an error when buffer is exhausted.

---

### 7. Resource Leak in Plugin Discovery
**Location:** `libs/zig/jn-discovery/src/discovery.zig:261-265`

```zig
const result = try child.wait();
if (result.Exited != 0) {
    return null;  // stdout/stderr readers may not be cleaned up
}
```

On early returns, spawned child process resources may not be fully cleaned up.

**Fix:** Use `defer` patterns consistently for child process cleanup.

---

### 8. Unclear API Ownership Semantics
**Location:** `tools/zig/jn-cat/main.zig:322-366`

The `createReader` function returns a struct containing slices, but ownership/lifetime is unclear:

```zig
pub fn createReader(...) !struct { reader: StreamReader, plugin_path: ?[]const u8 } {
    // plugin_path allocated by allocator, but caller doesn't know to free it
```

**Fix:** Document ownership in function comments, or use explicit Owned/Borrowed types.

---

### 9. ArrayList Initialization Pattern
**Location:** `plugins/zig/yaml/main.zig:62`

```zig
var stack = std.ArrayList(usize).init(allocator);
```

This allocates but doesn't ensure cleanup on all error paths.

**Fix:** Add `errdefer stack.deinit();` immediately after initialization.

---

### 10. Cache File Size Limit
**Location:** `libs/zig/jn-discovery/src/cache.zig:67`

```zig
const content = file.readToEndAlloc(allocator, 1024 * 1024) catch return null;
```

1MB cache limit is arbitrary. Large plugin directories could exceed this.

**Fix:** Make configurable or document the limit.

---

### 11. Hash Collision in group_by Keys
**Location:** `zq/src/main.zig:2547-2554`

```zig
switch (key_val) {
    .string => |s| key_str = s,
    .integer => |i| key_str = try std.fmt.allocPrint(allocator, "{d}", .{i}),
    // ...
}
```

Converting all types to strings for hash keys causes collisions between `"1"` (string) and `1` (integer).

**Fix:** Use a tagged union or type-prefixed keys.

---

## Medium Priority Issues (7)

### 12. Silent Error Swallowing in Streaming Mode
**Location:** `zq/src/main.zig:3034-3037`

```zig
const results = evalExpr(arena.allocator(), &expr, value) catch |err| {
    std.debug.print("Evaluation error: {}\n", .{err});
    continue;  // Silently continues to next record
};
```

Evaluation errors are printed but swallowed, making debugging difficult.

**Fix:** Add `--strict` mode that fails fast, or log to stderr with record context.

---

### 13. Missing Bounds Check in Conditional Parsing
**Location:** `zq/src/main.zig:821-827`

```zig
while (i + 4 < trimmed.len) : (i += 1) {
    // ...
    if (paren_depth == 0 and std.mem.eql(u8, trimmed[i .. i + 5], " then")) {
```

Accesses `i + 5` when loop only guarantees `i + 4 < trimmed.len`.

**Fix:** Change condition to `i + 5 <= trimmed.len`.

---

### 14. Thread Safety Not Documented
**Location:** Multiple files

None of the library APIs document their thread safety guarantees. Most are not thread-safe due to arena allocator usage.

**Fix:** Add `// Thread Safety: Not thread-safe` comments to public APIs.

---

### 15. Complexity in Address Parsing
**Location:** `libs/zig/jn-address/src/address.zig`

The `parse()` function is 200+ lines with deeply nested conditionals. McCabe complexity is high.

**Fix:** Break into smaller functions: `parseUrl()`, `parseGlob()`, `parseProfile()`, etc.

---

### 16. Missing Tests for Error Paths
**Location:** Multiple files

Most tests cover happy paths. Error handling code (network failures, malformed input, resource exhaustion) lacks test coverage.

**Fix:** Add negative test cases for each error variant.

---

### 17. TOML Parsing in PEP 723
**Location:** `libs/zig/jn-discovery/src/pep723.zig:89-120`

Manual TOML parsing is fragile and doesn't handle all valid TOML syntax (multiline strings, escape sequences, etc.).

**Fix:** Document limitations or use a proper TOML parser.

---

### 18. Potential Stack Overflow in Recursive Parsing
**Location:** `zq/src/main.zig:parseExprWithContext`

Deeply nested expressions cause recursive parsing that could overflow stack:

```zig
fn parseExprWithContext(allocator: std.mem.Allocator, expr: []const u8, err_ctx: *ErrorContext) ParseError!Expr {
    // Recursive calls to self for pipes, alternatives, etc.
```

**Fix:** Add recursion depth limit or convert to iterative parsing.

---

## Low Priority Issues (5)

### 19. Inconsistent Error Handling Patterns
**Location:** Various

Some functions return `error.X`, others return `null`, others exit the process. Inconsistent patterns make error handling unpredictable.

---

### 20. Magic Numbers
**Location:** Various

Hardcoded values like `64 * 1024` (buffer size), `1024 * 1024` (cache limit), `1024` (max args) should be named constants.

---

### 21. Redundant Code in jn-join
**Location:** `tools/zig/jn-join/main.zig`

Similar patterns repeated for left/right side processing could be deduplicated.

---

### 22. Missing --verbose Flag
**Location:** Most tools

No way to enable debug output for troubleshooting pipeline issues.

---

### 23. Version Compatibility Check
**Location:** `zq/src/main.zig:9-27`

The Zig version check for 0.15.1 vs 0.15.2 API differences is good, but should be extracted to a shared utility.

---

## Positive Observations

1. **Arena allocators used consistently** - Good memory management pattern
2. **Proper use of `defer`** - Resource cleanup is generally well-handled
3. **Comprehensive test suite for ZQ** - ~50 unit tests covering parser and evaluator
4. **Good error messages** - Unsupported jq features provide helpful suggestions
5. **Version compatibility handling** - Nice pattern for Zig version differences

---

## Recommendations

### Immediate Actions (Before Production)
1. Fix shell injection vulnerability in jn-cat
2. Fix integer overflow in fabs and shell buffer
3. Address global mutable state in jn-sh

### Short-term (Next Sprint)
4. Add errdefer to all allocations
5. Document ownership semantics
6. Add --strict mode to ZQ

### Long-term
7. Increase test coverage for error paths
8. Add fuzzing for parsers
9. Consider adding static analysis to CI
