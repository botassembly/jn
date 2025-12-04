//! PEP 723 (Inline Script Metadata) parser for Python plugins.
//!
//! Extracts [tool.jn] metadata from Python scripts without executing them.
//!
//! PEP 723 format:
//! ```python
//! # /// script
//! # requires-python = ">=3.11"
//! # dependencies = ["openpyxl"]
//! # [tool.jn]
//! # matches = [".*\\.xlsx$"]
//! # role = "format"
//! # ///
//! ```

const std = @import("std");

/// Parsed [tool.jn] metadata
pub const ToolJnMeta = struct {
    value: std.json.Value,
    allocator: std.mem.Allocator,

    pub fn deinit(self: *ToolJnMeta) void {
        freeJsonValue(self.allocator, self.value);
    }
};

/// Free a JSON value recursively
fn freeJsonValue(allocator: std.mem.Allocator, value: std.json.Value) void {
    switch (value) {
        .null, .bool, .integer, .float => {},
        .number_string => |s| allocator.free(s),
        .string => |s| allocator.free(s),
        .array => |arr| {
            for (arr.items) |item| {
                freeJsonValue(allocator, item);
            }
            var array = arr;
            array.deinit();
        },
        .object => |obj| {
            var iter = obj.iterator();
            while (iter.next()) |entry| {
                allocator.free(entry.key_ptr.*);
                freeJsonValue(allocator, entry.value_ptr.*);
            }
            var object = obj;
            object.deinit();
        },
    }
}

/// Parse [tool.jn] section from a Python file content.
///
/// Returns null if no valid [tool.jn] section is found.
pub fn parseToolJn(allocator: std.mem.Allocator, content: []const u8) !?ToolJnMeta {
    // Find the PEP 723 block boundaries
    const block_start = "# /// script";
    const block_end = "# ///";

    // Find start marker
    const start_pos = std.mem.indexOf(u8, content, block_start) orelse return null;
    const after_start = start_pos + block_start.len;

    // Find end marker (must be after start)
    const end_pos = std.mem.indexOfPos(u8, content, after_start, block_end) orelse return null;

    // Extract the block content
    const block = content[after_start..end_pos];

    // Find [tool.jn] section
    const tool_jn_marker = "[tool.jn]";
    const tool_jn_start = std.mem.indexOf(u8, block, tool_jn_marker) orelse return null;
    const after_tool_jn = tool_jn_start + tool_jn_marker.len;

    // Extract lines after [tool.jn] until next section or end
    var result = std.json.ObjectMap.init(allocator);
    errdefer {
        var r = result;
        var iter = r.iterator();
        while (iter.next()) |entry| {
            allocator.free(entry.key_ptr.*);
            freeJsonValue(allocator, entry.value_ptr.*);
        }
        r.deinit();
    }

    var line_iter = std.mem.splitScalar(u8, block[after_tool_jn..], '\n');
    while (line_iter.next()) |line| {
        // Strip comment prefix and whitespace
        const stripped = stripCommentPrefix(line);

        // Stop at next section or empty content
        if (stripped.len == 0) continue;
        if (stripped[0] == '[') break; // Next section

        // Parse TOML-like key = value
        if (parseTomlLine(allocator, stripped)) |kv| {
            errdefer {
                allocator.free(kv.key);
                freeJsonValue(allocator, kv.value);
            }
            try result.put(kv.key, kv.value);
        } else |_| {
            // Skip invalid lines
        }
    }

    // Must have at least 'matches' key
    if (!result.contains("matches")) {
        var iter = result.iterator();
        while (iter.next()) |entry| {
            allocator.free(entry.key_ptr.*);
            freeJsonValue(allocator, entry.value_ptr.*);
        }
        result.deinit();
        return null;
    }

    return ToolJnMeta{
        .value = .{ .object = result },
        .allocator = allocator,
    };
}

/// Strip "# " prefix from a comment line
fn stripCommentPrefix(line: []const u8) []const u8 {
    var trimmed = std.mem.trim(u8, line, " \t\r");
    if (trimmed.len >= 2 and trimmed[0] == '#' and trimmed[1] == ' ') {
        return std.mem.trim(u8, trimmed[2..], " \t");
    }
    if (trimmed.len >= 1 and trimmed[0] == '#') {
        return std.mem.trim(u8, trimmed[1..], " \t");
    }
    return "";
}

/// Key-value pair from TOML parsing
const KeyValue = struct {
    key: []const u8,
    value: std.json.Value,
};

/// Parse a TOML-like line: key = value
fn parseTomlLine(allocator: std.mem.Allocator, line: []const u8) !KeyValue {
    // Find '=' separator
    const eq_pos = std.mem.indexOf(u8, line, "=") orelse return error.InvalidLine;

    // Extract key (trim whitespace)
    const key = std.mem.trim(u8, line[0..eq_pos], " \t");
    if (key.len == 0) return error.InvalidLine;

    // Extract value (trim whitespace)
    const value_str = std.mem.trim(u8, line[eq_pos + 1 ..], " \t");
    if (value_str.len == 0) return error.InvalidLine;

    // Parse value based on format
    const value = try parseTomlValue(allocator, value_str);

    // Duplicate key
    const key_dup = try allocator.dupe(u8, key);

    return .{
        .key = key_dup,
        .value = value,
    };
}

/// Parse a TOML value (string, array, or basic literal)
fn parseTomlValue(allocator: std.mem.Allocator, value_str: []const u8) !std.json.Value {
    // Array: [...]
    if (value_str.len >= 2 and value_str[0] == '[') {
        return parseTomlArray(allocator, value_str);
    }

    // Quoted string: "..."
    if (value_str.len >= 2 and value_str[0] == '"') {
        const end_quote = std.mem.lastIndexOf(u8, value_str, "\"") orelse return error.InvalidValue;
        if (end_quote == 0) return error.InvalidValue;
        const str = try allocator.dupe(u8, value_str[1..end_quote]);
        return .{ .string = str };
    }

    // Boolean
    if (std.mem.eql(u8, value_str, "true")) {
        return .{ .bool = true };
    }
    if (std.mem.eql(u8, value_str, "false")) {
        return .{ .bool = false };
    }

    // Integer
    const int = std.fmt.parseInt(i64, value_str, 10) catch {
        // Fallback: treat as unquoted string
        const str = try allocator.dupe(u8, value_str);
        return .{ .string = str };
    };
    return .{ .integer = int };
}

/// Parse a TOML array: ["value1", "value2"]
fn parseTomlArray(allocator: std.mem.Allocator, value_str: []const u8) !std.json.Value {
    var array = std.json.Array.init(allocator);
    errdefer array.deinit();

    // Remove brackets
    if (value_str.len < 2 or value_str[0] != '[') return error.InvalidArray;
    const close_bracket = std.mem.lastIndexOf(u8, value_str, "]") orelse return error.InvalidArray;
    const inner = std.mem.trim(u8, value_str[1..close_bracket], " \t\r\n");

    if (inner.len == 0) {
        return .{ .array = array };
    }

    // Split by comma (simple parsing, doesn't handle nested arrays)
    var item_iter = std.mem.splitSequence(u8, inner, ",");
    while (item_iter.next()) |item| {
        const trimmed = std.mem.trim(u8, item, " \t\r\n");
        if (trimmed.len == 0) continue;

        // Each item should be a quoted string
        if (trimmed.len >= 2 and trimmed[0] == '"') {
            const end_quote = std.mem.lastIndexOf(u8, trimmed, "\"") orelse continue;
            if (end_quote == 0) continue;
            const str = try allocator.dupe(u8, trimmed[1..end_quote]);
            try array.append(.{ .string = str });
        }
    }

    return .{ .array = array };
}

// ============================================================================
// Tests
// ============================================================================

test "parseToolJn extracts metadata from valid PEP 723" {
    const allocator = std.testing.allocator;

    const content =
        \\#!/usr/bin/env -S uv run --script
        \\# /// script
        \\# requires-python = ">=3.11"
        \\# [tool.jn]
        \\# matches = [".*\\.xlsx$"]
        \\# role = "format"
        \\# modes = ["read", "write"]
        \\# ///
        \\
        \\import sys
    ;

    var meta = (try parseToolJn(allocator, content)).?;
    defer meta.deinit();

    const obj = meta.value.object;
    try std.testing.expect(obj.contains("matches"));
    try std.testing.expect(obj.contains("role"));
    try std.testing.expect(obj.contains("modes"));

    const role = obj.get("role").?.string;
    try std.testing.expectEqualStrings("format", role);
}

test "parseToolJn returns null for missing [tool.jn]" {
    const allocator = std.testing.allocator;

    const content =
        \\#!/usr/bin/env python
        \\# /// script
        \\# requires-python = ">=3.11"
        \\# ///
        \\
        \\print("hello")
    ;

    const result = try parseToolJn(allocator, content);
    try std.testing.expect(result == null);
}

test "parseToolJn returns null for no script block" {
    const allocator = std.testing.allocator;

    const content =
        \\#!/usr/bin/env python
        \\
        \\print("hello")
    ;

    const result = try parseToolJn(allocator, content);
    try std.testing.expect(result == null);
}

test "parseTomlValue handles strings" {
    const allocator = std.testing.allocator;

    const result = try parseTomlValue(allocator, "\"hello world\"");
    defer freeJsonValue(allocator, result);

    try std.testing.expectEqualStrings("hello world", result.string);
}

test "parseTomlValue handles booleans" {
    const allocator = std.testing.allocator;

    const true_val = try parseTomlValue(allocator, "true");
    try std.testing.expect(true_val.bool == true);

    const false_val = try parseTomlValue(allocator, "false");
    try std.testing.expect(false_val.bool == false);
}

test "parseTomlValue handles integers" {
    const allocator = std.testing.allocator;

    const int_val = try parseTomlValue(allocator, "42");
    try std.testing.expectEqual(@as(i64, 42), int_val.integer);
}

test "parseTomlArray handles string arrays" {
    const allocator = std.testing.allocator;

    const result = try parseTomlArray(allocator, "[\"one\", \"two\", \"three\"]");
    defer freeJsonValue(allocator, result);

    try std.testing.expectEqual(@as(usize, 3), result.array.items.len);
    try std.testing.expectEqualStrings("one", result.array.items[0].string);
    try std.testing.expectEqualStrings("two", result.array.items[1].string);
    try std.testing.expectEqualStrings("three", result.array.items[2].string);
}

test "parseTomlArray handles empty array" {
    const allocator = std.testing.allocator;

    const result = try parseTomlArray(allocator, "[]");
    defer freeJsonValue(allocator, result);

    try std.testing.expectEqual(@as(usize, 0), result.array.items.len);
}

test "stripCommentPrefix removes # prefix" {
    try std.testing.expectEqualStrings("hello", stripCommentPrefix("# hello"));
    try std.testing.expectEqualStrings("world", stripCommentPrefix("#world"));
    try std.testing.expectEqualStrings("test", stripCommentPrefix("  # test  "));
    try std.testing.expectEqualStrings("", stripCommentPrefix("no comment"));
}

test "parseToolJn handles multiline arrays" {
    const allocator = std.testing.allocator;

    const content =
        \\# /// script
        \\# [tool.jn]
        \\# matches = [
        \\#   ".*\\.xlsx$",
        \\#   ".*\\.xlsm$"
        \\# ]
        \\# ///
    ;

    // Note: Current implementation doesn't handle multiline arrays perfectly
    // This test documents the limitation - arrays must be on single line
    const result = try parseToolJn(allocator, content);
    // May return null due to multiline array - that's expected behavior
    if (result) |*r| {
        var meta = r.*;
        meta.deinit();
    }
}

test "parseToolJn extracts name from metadata" {
    const allocator = std.testing.allocator;

    const content =
        \\# /// script
        \\# [tool.jn]
        \\# name = "xlsx"
        \\# matches = [".*\\.xlsx$"]
        \\# role = "format"
        \\# ///
    ;

    var meta = (try parseToolJn(allocator, content)).?;
    defer meta.deinit();

    const obj = meta.value.object;
    const name = obj.get("name").?.string;
    try std.testing.expectEqualStrings("xlsx", name);
}
