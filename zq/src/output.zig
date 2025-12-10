const std = @import("std");
const types = @import("types.zig");

const Config = types.Config;

// ============================================================================
// Output
// ============================================================================

pub fn writeJson(allocator: std.mem.Allocator, writer: anytype, value: std.json.Value, config: Config) !void {
    _ = allocator; // Arena allocator available if needed
    if (config.raw_strings) {
        switch (value) {
            .string => |s| {
                try writer.writeAll(s);
                return;
            },
            else => {},
        }
    }
    try writeJsonValue(writer, value);
}

pub fn writeJsonValue(writer: anytype, value: std.json.Value) !void {
    switch (value) {
        .null => try writer.writeAll("null"),
        .bool => |b| try writer.writeAll(if (b) "true" else "false"),
        .integer => |i| try writer.print("{d}", .{i}),
        .float => |f| {
            // Handle special cases for JSON compatibility
            if (std.math.isNan(f) or std.math.isInf(f)) {
                try writer.writeAll("null");
            } else {
                try writer.print("{d}", .{f});
            }
        },
        .number_string => |s| try writer.writeAll(s),
        .string => |s| {
            try writer.writeByte('"');
            // Batch writes for runs of safe characters (3x faster than char-by-char)
            var start: usize = 0;
            for (s, 0..) |c, i| {
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
        },
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
            var first = true;
            var iter = obj.iterator();
            while (iter.next()) |entry| {
                if (!first) try writer.writeByte(',');
                first = false;
                try writer.writeByte('"');
                try writer.writeAll(entry.key_ptr.*);
                try writer.writeAll("\":");
                try writeJsonValue(writer, entry.value_ptr.*);
            }
            try writer.writeByte('}');
        },
    }
}
