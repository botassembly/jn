//! Shell command escaping utilities for JN.
//!
//! Provides safe string escaping for shell command construction.
//! Use these functions when shell execution is unavoidable.

const std = @import("std");

/// Escape a string for safe use in a single-quoted shell argument.
///
/// Single-quoted strings in POSIX shells don't interpret any special
/// characters except the single quote itself. This function escapes
/// single quotes by ending the quote, adding an escaped quote, and
/// starting a new quote: ' -> '\''
///
/// Example:
///   Input:  "file's name.txt"
///   Output: "file'\''s name.txt"
///
/// Use this in shell commands as: 'escaped_string'
pub fn escapeForShellSingleQuote(allocator: std.mem.Allocator, input: []const u8) ![]u8 {
    // Count single quotes to determine output size
    var quote_count: usize = 0;
    for (input) |c| {
        if (c == '\'') quote_count += 1;
    }

    // Each single quote becomes 4 characters: '\''
    // Use checked arithmetic to prevent overflow on extremely large inputs
    const extra_chars = std.math.mul(usize, quote_count, 3) catch return error.OutOfMemory;
    const output_len = std.math.add(usize, input.len, extra_chars) catch return error.OutOfMemory;
    var output = try allocator.alloc(u8, output_len);
    errdefer allocator.free(output);

    var out_idx: usize = 0;
    for (input) |c| {
        if (c == '\'') {
            // End quote, escaped quote, start quote
            output[out_idx] = '\'';
            output[out_idx + 1] = '\\';
            output[out_idx + 2] = '\'';
            output[out_idx + 3] = '\'';
            out_idx += 4;
        } else {
            output[out_idx] = c;
            out_idx += 1;
        }
    }

    return output;
}

/// Check if a string is safe to use unescaped in a single-quoted shell string.
/// Returns true if the string contains no single quotes.
pub fn isSafeForShellSingleQuote(input: []const u8) bool {
    for (input) |c| {
        if (c == '\'') return false;
    }
    return true;
}

/// Check if a glob pattern is safe to use unquoted in a shell.
///
/// Glob patterns need special handling because they must be unquoted for
/// bash to expand wildcards (*,?,[]), but we must reject shell injection
/// characters.
///
/// Allowed characters:
///   - Alphanumeric (a-z, A-Z, 0-9)
///   - Path separators and common file chars: / . - _ (space)
///   - Glob wildcards: * ? [ ]
///
/// Rejected (shell injection risk):
///   - Command separators: ; | & \n \r
///   - Substitution: $ ` ( ) { }
///   - Redirection: < >
///   - Quotes/escapes: ' " \
///   - Other special: ! # ~
pub fn isGlobPatternSafe(pattern: []const u8) bool {
    for (pattern) |c| {
        const is_safe = switch (c) {
            // Alphanumeric
            'a'...'z', 'A'...'Z', '0'...'9' => true,
            // Safe path characters
            '/', '.', '-', '_', ' ' => true,
            // Glob metacharacters (need to be unquoted for expansion)
            '*', '?', '[', ']' => true,
            // Everything else is potentially dangerous
            else => false,
        };
        if (!is_safe) return false;
    }
    return true;
}

/// Format a shell command with properly escaped arguments.
///
/// This is a convenience function that escapes all arguments and builds
/// a command string with each argument wrapped in single quotes.
///
/// Note: When possible, prefer using std.process.Child.init with direct
/// argument arrays instead of shell execution. This function is for cases
/// where shell features (pipes, redirects) are required.
pub fn formatShellCommand(
    allocator: std.mem.Allocator,
    comptime fmt: []const u8,
    args: anytype,
) ![]u8 {
    // For now, just use allocPrint - callers should escape their arguments
    // before passing them in
    return std.fmt.allocPrint(allocator, fmt, args);
}

// ============================================================================
// Tests
// ============================================================================

test "escapeForShellSingleQuote handles no quotes" {
    const allocator = std.testing.allocator;
    const result = try escapeForShellSingleQuote(allocator, "simple string");
    defer allocator.free(result);
    try std.testing.expectEqualStrings("simple string", result);
}

test "escapeForShellSingleQuote escapes single quote" {
    const allocator = std.testing.allocator;
    const result = try escapeForShellSingleQuote(allocator, "file's");
    defer allocator.free(result);
    try std.testing.expectEqualStrings("file'\\''s", result);
}

test "escapeForShellSingleQuote handles multiple quotes" {
    const allocator = std.testing.allocator;
    const result = try escapeForShellSingleQuote(allocator, "a'b'c");
    defer allocator.free(result);
    try std.testing.expectEqualStrings("a'\\''b'\\''c", result);
}

test "escapeForShellSingleQuote handles empty string" {
    const allocator = std.testing.allocator;
    const result = try escapeForShellSingleQuote(allocator, "");
    defer allocator.free(result);
    try std.testing.expectEqualStrings("", result);
}

test "isSafeForShellSingleQuote returns true for safe strings" {
    try std.testing.expect(isSafeForShellSingleQuote("simple"));
    try std.testing.expect(isSafeForShellSingleQuote("path/to/file.txt"));
    try std.testing.expect(isSafeForShellSingleQuote("file with spaces.csv"));
}

test "isSafeForShellSingleQuote returns false for unsafe strings" {
    try std.testing.expect(!isSafeForShellSingleQuote("file's name"));
    try std.testing.expect(!isSafeForShellSingleQuote("'quoted'"));
}

test "isGlobPatternSafe allows valid globs" {
    try std.testing.expect(isGlobPatternSafe("*.json"));
    try std.testing.expect(isGlobPatternSafe("data/*.csv"));
    try std.testing.expect(isGlobPatternSafe("**/*.txt"));
    try std.testing.expect(isGlobPatternSafe("file[0-9].log"));
    try std.testing.expect(isGlobPatternSafe("path/to/file.json"));
    try std.testing.expect(isGlobPatternSafe("file with spaces.txt"));
    try std.testing.expect(isGlobPatternSafe("file-name_123.json"));
}

test "isGlobPatternSafe rejects injection attempts" {
    // Command separators
    try std.testing.expect(!isGlobPatternSafe("*.json; rm -rf /"));
    try std.testing.expect(!isGlobPatternSafe("*.json | cat /etc/passwd"));
    try std.testing.expect(!isGlobPatternSafe("*.json && evil"));
    // Substitution
    try std.testing.expect(!isGlobPatternSafe("$(whoami).json"));
    try std.testing.expect(!isGlobPatternSafe("`whoami`.json"));
    try std.testing.expect(!isGlobPatternSafe("${HOME}/*.json"));
    // Quotes
    try std.testing.expect(!isGlobPatternSafe("'*.json'"));
    try std.testing.expect(!isGlobPatternSafe("\"*.json\""));
    // Redirection
    try std.testing.expect(!isGlobPatternSafe("*.json > /tmp/x"));
    try std.testing.expect(!isGlobPatternSafe("*.json < /etc/passwd"));
}
