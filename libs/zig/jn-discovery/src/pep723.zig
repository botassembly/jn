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
//!
//! Supports multi-line arrays:
//! ```python
//! # matches = [
//! #   ".*\\.csv$",
//! #   ".*\\.tsv$"
//! # ]
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

    // Collect all stripped lines for multi-line parsing
    var lines: std.ArrayListUnmanaged([]const u8) = .empty;
    defer lines.deinit(allocator);

    var line_iter = std.mem.splitScalar(u8, block[after_tool_jn..], '\n');
    while (line_iter.next()) |line| {
        const stripped = stripCommentPrefix(line);
        if (stripped.len == 0) continue;
        if (stripped[0] == '[') break; // Next section
        try lines.append(allocator, stripped);
    }

    // Parse lines with multi-line array support
    var i: usize = 0;
    while (i < lines.items.len) {
        const line = lines.items[i];

        // Find '=' separator
        const eq_pos = std.mem.indexOf(u8, line, "=") orelse {
            i += 1;
            continue;
        };

        const key = std.mem.trim(u8, line[0..eq_pos], " \t");
        if (key.len == 0) {
            i += 1;
            continue;
        }

        var value_str = std.mem.trim(u8, line[eq_pos + 1 ..], " \t");

        // Check if this is a multi-line array (starts with [ but doesn't end with ])
        if (value_str.len > 0 and value_str[0] == '[') {
            if (std.mem.indexOf(u8, value_str, "]") == null) {
                // Multi-line array - accumulate lines until we find ]
                var array_buf: std.ArrayListUnmanaged(u8) = .empty;
                defer array_buf.deinit(allocator);

                // Add first line
                try array_buf.appendSlice(allocator, value_str);

                // Keep adding lines until we find closing ]
                // Note: We look for ] as the last non-whitespace char to avoid
                // matching ] inside strings like ".*[*?].*"
                i += 1;
                while (i < lines.items.len) {
                    const next_line = lines.items[i];
                    try array_buf.append(allocator, ' '); // Join with space
                    try array_buf.appendSlice(allocator, next_line);
                    if (isArrayClosingLine(next_line)) {
                        i += 1;
                        break;
                    }
                    i += 1;
                }

                value_str = array_buf.items;

                // Parse the accumulated array
                const value = parseTomlValue(allocator, value_str) catch {
                    continue;
                };
                const key_dup = try allocator.dupe(u8, key);
                errdefer allocator.free(key_dup);
                try result.put(key_dup, value);
                continue;
            }
        }

        // Single-line value
        const value = parseTomlValue(allocator, value_str) catch {
            i += 1;
            continue;
        };
        const key_dup = try allocator.dupe(u8, key);
        errdefer allocator.free(key_dup);
        try result.put(key_dup, value);
        i += 1;
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

/// Check if a line ends the TOML array (has ] as last non-whitespace char)
/// This avoids matching ] inside strings like ".*[*?].*"
fn isArrayClosingLine(line: []const u8) bool {
    const trimmed = std.mem.trimRight(u8, line, " \t\r");
    if (trimmed.len == 0) return false;
    return trimmed[trimmed.len - 1] == ']';
}

/// Unescape TOML basic string escape sequences
/// Handles: \\ -> \, \" -> ", \n -> newline, \t -> tab
fn unescapeTomlString(allocator: std.mem.Allocator, raw: []const u8) ![]u8 {
    var result = try allocator.alloc(u8, raw.len);
    var result_len: usize = 0;
    var i: usize = 0;

    while (i < raw.len) {
        if (raw[i] == '\\' and i + 1 < raw.len) {
            const next = raw[i + 1];
            switch (next) {
                '\\' => {
                    result[result_len] = '\\';
                    result_len += 1;
                    i += 2;
                },
                '"' => {
                    result[result_len] = '"';
                    result_len += 1;
                    i += 2;
                },
                'n' => {
                    result[result_len] = '\n';
                    result_len += 1;
                    i += 2;
                },
                't' => {
                    result[result_len] = '\t';
                    result_len += 1;
                    i += 2;
                },
                else => {
                    // Unknown escape, keep as-is
                    result[result_len] = raw[i];
                    result_len += 1;
                    i += 1;
                },
            }
        } else {
            result[result_len] = raw[i];
            result_len += 1;
            i += 1;
        }
    }

    // Shrink to actual size
    return allocator.realloc(result, result_len);
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
        const raw = value_str[1..end_quote];
        const str = try unescapeTomlString(allocator, raw);
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
            const raw = trimmed[1..end_quote];
            const str = try unescapeTomlString(allocator, raw);
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
        \\# role = "format"
        \\# ///
    ;

    var meta = (try parseToolJn(allocator, content)).?;
    defer meta.deinit();

    const obj = meta.value.object;
    try std.testing.expect(obj.contains("matches"));

    const matches = obj.get("matches").?.array;
    try std.testing.expectEqual(@as(usize, 2), matches.items.len);
    try std.testing.expectEqualStrings(".*\\.xlsx$", matches.items[0].string);
    try std.testing.expectEqualStrings(".*\\.xlsm$", matches.items[1].string);
}

test "parseToolJn handles watch_shell style multiline" {
    const allocator = std.testing.allocator;

    // Exact format from watch_shell.py
    const content =
        \\#!/usr/bin/env -S uv run --script
        \\# /// script
        \\# requires-python = ">=3.11"
        \\# dependencies = ["watchfiles>=0.21"]
        \\# [tool.jn]
        \\# matches = [
        \\#   "^watch($| )", "^watch .*",
        \\#   "^watchfiles($| )", "^watchfiles .*"
        \\# ]
        \\# ///
    ;

    var meta = (try parseToolJn(allocator, content)).?;
    defer meta.deinit();

    const obj = meta.value.object;
    const matches = obj.get("matches").?.array;
    try std.testing.expectEqual(@as(usize, 4), matches.items.len);
    try std.testing.expectEqualStrings("^watch($| )", matches.items[0].string);
    try std.testing.expectEqualStrings("^watch .*", matches.items[1].string);
}

test "parseToolJn handles glob style multiline" {
    const allocator = std.testing.allocator;

    const content =
        \\# /// script
        \\# [tool.jn]
        \\# type = "protocol"
        \\# matches = [
        \\#   "^glob://.*",
        \\#   ".*[*?].*",
        \\#   ".*\\*\\*.*"
        \\# ]
        \\# ///
    ;

    var meta = (try parseToolJn(allocator, content)).?;
    defer meta.deinit();

    const obj = meta.value.object;
    const matches = obj.get("matches").?.array;
    try std.testing.expectEqual(@as(usize, 3), matches.items.len);
    try std.testing.expectEqualStrings("^glob://.*", matches.items[0].string);
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
