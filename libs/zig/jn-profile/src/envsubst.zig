//! Environment variable substitution for JN profiles.
//!
//! Supports:
//! - ${VAR} - replaced with environment variable value
//! - ${VAR:-default} - use default if VAR is unset or empty
//!
//! Example:
//!   "Bearer ${API_TOKEN}" -> "Bearer sk-xxxx"
//!   "${TIMEOUT:-30}" -> "30" (if TIMEOUT is unset)

const std = @import("std");

/// Substitute environment variables in a string.
///
/// Returns a newly allocated string with all ${VAR} and ${VAR:-default}
/// patterns replaced. The caller owns the returned memory.
pub fn substitute(allocator: std.mem.Allocator, input: []const u8) ![]u8 {
    var result: std.ArrayListUnmanaged(u8) = .empty;
    errdefer result.deinit(allocator);

    var i: usize = 0;
    while (i < input.len) {
        // Look for ${
        if (i + 1 < input.len and input[i] == '$' and input[i + 1] == '{') {
            // Find closing }
            const start = i + 2;
            var end = start;
            while (end < input.len and input[end] != '}') : (end += 1) {}

            if (end < input.len) {
                // Extract variable expression
                const expr = input[start..end];
                const value = resolveExpression(expr);
                try result.appendSlice(allocator, value);
                i = end + 1;
            } else {
                // No closing }, treat as literal
                try result.append(allocator, input[i]);
                i += 1;
            }
        } else {
            try result.append(allocator, input[i]);
            i += 1;
        }
    }

    return result.toOwnedSlice(allocator);
}

/// Resolve a variable expression (without the ${}).
///
/// Handles:
/// - VAR -> getenv("VAR")
/// - VAR:-default -> getenv("VAR") or "default"
fn resolveExpression(expr: []const u8) []const u8 {
    // Check for :- default syntax
    if (std.mem.indexOf(u8, expr, ":-")) |sep| {
        const var_name = expr[0..sep];
        const default = expr[sep + 2 ..];

        if (std.posix.getenv(var_name)) |value| {
            if (value.len > 0) {
                return value;
            }
        }
        return default;
    }

    // Simple variable lookup
    return std.posix.getenv(expr) orelse "";
}

/// Substitute environment variables in a JSON value recursively.
///
/// Only substitutes in string values. Arrays and objects are traversed.
/// The input JSON value is modified in place (string pointers are replaced).
pub fn substituteJsonValue(allocator: std.mem.Allocator, value: *std.json.Value) !void {
    switch (value.*) {
        .string => |s| {
            // Only substitute if the string contains ${
            if (std.mem.indexOf(u8, s, "${") != null) {
                const substituted = try substitute(allocator, s);
                value.* = .{ .string = substituted };
            }
        },
        .array => |arr| {
            for (arr.items) |*item| {
                try substituteJsonValue(allocator, item);
            }
        },
        .object => |*obj| {
            var iter = obj.iterator();
            while (iter.next()) |entry| {
                try substituteJsonValue(allocator, entry.value_ptr);
            }
        },
        else => {}, // null, bool, integer, float - no substitution
    }
}

// ============================================================================
// Tests
// ============================================================================

test "substitute simple variable" {
    // Set a test environment variable
    // Note: In Zig tests, we can't easily set env vars, so we test the parsing logic
    const allocator = std.testing.allocator;

    // Test literal string (no substitution)
    const literal = try substitute(allocator, "hello world");
    defer allocator.free(literal);
    try std.testing.expectEqualStrings("hello world", literal);
}

test "substitute with default value" {
    const allocator = std.testing.allocator;

    // Test default value when env var is not set
    // UNLIKELY_VAR_NAME_12345 should not exist
    const result = try substitute(allocator, "value=${UNLIKELY_VAR_NAME_12345:-default_value}");
    defer allocator.free(result);
    try std.testing.expectEqualStrings("value=default_value", result);
}

test "substitute preserves unmatched" {
    const allocator = std.testing.allocator;

    // Unclosed ${ should be preserved
    const result = try substitute(allocator, "unclosed ${VAR");
    defer allocator.free(result);
    try std.testing.expectEqualStrings("unclosed ${VAR", result);
}

test "substitute multiple variables" {
    const allocator = std.testing.allocator;

    const result = try substitute(allocator, "${A:-1} and ${B:-2}");
    defer allocator.free(result);
    try std.testing.expectEqualStrings("1 and 2", result);
}

test "substitute existing env var" {
    const allocator = std.testing.allocator;

    // PATH should always exist
    const result = try substitute(allocator, "path=${PATH}");
    defer allocator.free(result);

    // Should start with "path=" and have some content
    try std.testing.expect(std.mem.startsWith(u8, result, "path="));
    try std.testing.expect(result.len > 5); // path= + something
}

test "resolveExpression with default" {
    // Non-existent variable with default
    const val = resolveExpression("NONEXISTENT_VAR_XYZ:-fallback");
    try std.testing.expectEqualStrings("fallback", val);
}

test "resolveExpression without default" {
    // Non-existent variable without default returns empty
    const val = resolveExpression("NONEXISTENT_VAR_XYZ");
    try std.testing.expectEqualStrings("", val);
}
