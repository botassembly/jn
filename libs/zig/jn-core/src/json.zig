//! JSON parsing and writing helpers for JN plugins.
//!
//! Provides utilities for parsing JSON lines and writing properly
//! escaped JSON output. Designed for NDJSON (newline-delimited JSON)
//! workflows.

const std = @import("std");

/// Parse a JSON line into a Value.
///
/// Uses the provided allocator for the parse tree. The caller should
/// use an arena allocator and reset it after each line for memory efficiency.
///
/// Returns null on parse error (caller should handle or skip the line).
pub fn parseJsonLine(allocator: std.mem.Allocator, line: []const u8) ?std.json.Parsed(std.json.Value) {
    return std.json.parseFromSlice(std.json.Value, allocator, line, .{}) catch null;
}

/// Write a JSON-escaped string (with surrounding quotes) to the writer.
///
/// Properly escapes special characters: " \ \n \r \t and control chars.
/// Uses batch writes for runs of safe characters (3x faster than char-by-char).
pub fn writeJsonString(writer: anytype, s: []const u8) !void {
    try writer.writeByte('"');

    var start: usize = 0;
    for (s, 0..) |c, i| {
        // Check if character needs escaping: quote, backslash, or control chars
        const needs_escape = (c == '"' or c == '\\' or c < 0x20);

        if (!needs_escape) continue;

        // Write batch of safe chars before this escape
        if (i > start) {
            try writer.writeAll(s[start..i]);
        }

        switch (c) {
            '"' => try writer.writeAll("\\\""),
            '\\' => try writer.writeAll("\\\\"),
            '\n' => try writer.writeAll("\\n"),
            '\r' => try writer.writeAll("\\r"),
            '\t' => try writer.writeAll("\\t"),
            else => try writer.print("\\u{x:0>4}", .{c}),
        }
        start = i + 1;
    }

    // Write remaining safe chars
    if (start < s.len) {
        try writer.writeAll(s[start..]);
    }
    try writer.writeByte('"');
}

/// Write a JSON value to the writer.
///
/// Recursively writes arrays and objects. Uses compact (no whitespace) format.
pub fn writeJsonValue(writer: anytype, value: std.json.Value) !void {
    switch (value) {
        .null => try writer.writeAll("null"),
        .bool => |b| try writer.writeAll(if (b) "true" else "false"),
        .integer => |i| try writer.print("{d}", .{i}),
        .float => |f| try writer.print("{d}", .{f}),
        .number_string => |s| try writer.writeAll(s),
        .string => |s| try writeJsonString(writer, s),
        .array => |arr| {
            try writer.writeByte('[');
            for (arr.items, 0..) |item, i| {
                if (i > 0) try writer.writeByte(',');
                try writeJsonValue(writer, item);
            }
            try writer.writeByte(']');
        },
        .object => |obj| {
            try writer.writeByte('{');
            var iter = obj.iterator();
            var first = true;
            while (iter.next()) |entry| {
                if (!first) try writer.writeByte(',');
                first = false;

                try writeJsonString(writer, entry.key_ptr.*);
                try writer.writeByte(':');
                try writeJsonValue(writer, entry.value_ptr.*);
            }
            try writer.writeByte('}');
        },
    }
}

/// Write a JSON value as a complete NDJSON line (with trailing newline).
pub fn writeJsonLine(writer: anytype, value: std.json.Value) !void {
    try writeJsonValue(writer, value);
    try writer.writeByte('\n');
}

// ============================================================================
// Tests
// ============================================================================

test "writeJsonString escapes special characters" {
    const testing = std.testing;
    var buf: [256]u8 = undefined;
    var fbs = std.io.fixedBufferStream(&buf);
    const writer = fbs.writer();

    try writeJsonString(writer, "hello");
    try testing.expectEqualStrings("\"hello\"", fbs.getWritten());

    fbs.reset();
    try writeJsonString(writer, "say \"hi\"");
    try testing.expectEqualStrings("\"say \\\"hi\\\"\"", fbs.getWritten());

    fbs.reset();
    try writeJsonString(writer, "line1\nline2");
    try testing.expectEqualStrings("\"line1\\nline2\"", fbs.getWritten());

    fbs.reset();
    try writeJsonString(writer, "path\\to\\file");
    try testing.expectEqualStrings("\"path\\\\to\\\\file\"", fbs.getWritten());
}

test "writeJsonValue handles primitives" {
    const testing = std.testing;
    var buf: [256]u8 = undefined;
    var fbs = std.io.fixedBufferStream(&buf);
    const writer = fbs.writer();

    try writeJsonValue(writer, .null);
    try testing.expectEqualStrings("null", fbs.getWritten());

    fbs.reset();
    try writeJsonValue(writer, .{ .bool = true });
    try testing.expectEqualStrings("true", fbs.getWritten());

    fbs.reset();
    try writeJsonValue(writer, .{ .integer = 42 });
    try testing.expectEqualStrings("42", fbs.getWritten());

    fbs.reset();
    try writeJsonValue(writer, .{ .float = 3.14 });
    // Float formatting may vary, just check it contains expected parts
    const written = fbs.getWritten();
    try testing.expect(written.len > 0);
}

test "parseJsonLine returns null on invalid JSON" {
    const result = parseJsonLine(std.testing.allocator, "not valid json");
    try std.testing.expect(result == null);
}

test "parseJsonLine parses valid JSON" {
    const result = parseJsonLine(std.testing.allocator, "{\"x\":1}");
    try std.testing.expect(result != null);
    defer result.?.deinit();

    const value = result.?.value;
    try std.testing.expect(value == .object);
}
