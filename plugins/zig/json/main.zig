const std = @import("std");

// ============================================================================
// JSON Plugin - Standalone Zig plugin for JN
//
// Reads JSON files and outputs NDJSON records.
// - JSON array: Each element becomes an NDJSON line
// - JSON object: Output as single NDJSON line
//
// Write mode is passthrough (NDJSON is valid JSON lines).
// ============================================================================

const Plugin = struct {
    name: []const u8,
    version: []const u8,
    matches: []const []const u8,
    role: []const u8,
    modes: []const []const u8,
};

const plugin = Plugin{
    .name = "json",
    .version = "0.1.0",
    .matches = &[_][]const u8{".*\\.json$"},
    .role = "format",
    .modes = &[_][]const u8{"read"},  // Write mode uses Python json_ for indent support
};

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    // Parse command line arguments
    var args = std.process.args();
    _ = args.skip(); // Skip program name

    var mode: []const u8 = "read";
    var jn_meta = false;

    while (args.next()) |arg| {
        if (std.mem.eql(u8, arg, "--jn-meta")) {
            jn_meta = true;
        } else if (std.mem.startsWith(u8, arg, "--mode=")) {
            mode = arg["--mode=".len..];
        }
    }

    // Handle --jn-meta: output plugin manifest
    if (jn_meta) {
        try outputManifest();
        return;
    }

    // Dispatch based on mode
    if (std.mem.eql(u8, mode, "read")) {
        try readMode(allocator);
    } else if (std.mem.eql(u8, mode, "write")) {
        try writeMode();
    } else {
        std.debug.print("json: error: unknown mode '{s}'\n", .{mode});
        std.process.exit(1);
    }
}

fn outputManifest() !void {
    var stdout_buf: [4096]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    try writer.writeAll("{\"name\":\"");
    try writer.writeAll(plugin.name);
    try writer.writeAll("\",\"version\":\"");
    try writer.writeAll(plugin.version);
    try writer.writeAll("\",\"matches\":[");

    for (plugin.matches, 0..) |pattern, i| {
        if (i > 0) try writer.writeByte(',');
        try writer.writeByte('"');
        for (pattern) |c| {
            if (c == '"' or c == '\\') try writer.writeByte('\\');
            try writer.writeByte(c);
        }
        try writer.writeByte('"');
    }

    try writer.writeAll("],\"role\":\"");
    try writer.writeAll(plugin.role);
    try writer.writeAll("\",\"modes\":[");

    for (plugin.modes, 0..) |m, i| {
        if (i > 0) try writer.writeByte(',');
        try writer.writeByte('"');
        try writer.writeAll(m);
        try writer.writeByte('"');
    }

    try writer.writeAll("]}\n");
    try writer.flush();
}

// ============================================================================
// JSON Read Mode
// ============================================================================

fn readMode(allocator: std.mem.Allocator) !void {
    var stdin_buf: [64 * 1024]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [64 * 1024]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    // Read all input into memory (JSON needs full parsing)
    var input = std.ArrayListUnmanaged(u8){};
    defer input.deinit(allocator);

    while (true) {
        const maybe_line = reader.takeDelimiter('\n') catch |err| {
            std.debug.print("json: read error: {}\n", .{err});
            std.process.exit(1);
        };

        if (maybe_line) |line| {
            try input.appendSlice(allocator, line);
            try input.append(allocator, '\n');
        } else {
            break;
        }
    }

    if (input.items.len == 0) {
        try writer.flush();
        return;
    }

    // Parse JSON
    const parsed = std.json.parseFromSlice(std.json.Value, allocator, input.items, .{}) catch |err| {
        std.debug.print("json: parse error: {}\n", .{err});
        std.process.exit(1);
    };
    defer parsed.deinit();

    // Output as NDJSON
    switch (parsed.value) {
        .array => |arr| {
            // Each array element becomes a line
            for (arr.items) |item| {
                try writeJsonValue(writer, item, allocator);
                try writer.writeByte('\n');
            }
        },
        else => {
            // Single value becomes single line
            try writeJsonValue(writer, parsed.value, allocator);
            try writer.writeByte('\n');
        },
    }

    try writer.flush();
}

fn writeJsonValue(writer: anytype, value: std.json.Value, allocator: std.mem.Allocator) !void {
    switch (value) {
        .null => try writer.writeAll("null"),
        .bool => |b| try writer.writeAll(if (b) "true" else "false"),
        .integer => |i| try writer.print("{d}", .{i}),
        .float => |f| try writer.print("{d}", .{f}),
        .number_string => |s| try writer.writeAll(s),
        .string => |s| {
            try writer.writeByte('"');
            for (s) |c| {
                switch (c) {
                    '"' => try writer.writeAll("\\\""),
                    '\\' => try writer.writeAll("\\\\"),
                    '\n' => try writer.writeAll("\\n"),
                    '\r' => try writer.writeAll("\\r"),
                    '\t' => try writer.writeAll("\\t"),
                    else => {
                        if (c < 0x20) {
                            try writer.print("\\u{x:0>4}", .{c});
                        } else {
                            try writer.writeByte(c);
                        }
                    },
                }
            }
            try writer.writeByte('"');
        },
        .array => |arr| {
            try writer.writeByte('[');
            for (arr.items, 0..) |item, i| {
                if (i > 0) try writer.writeByte(',');
                try writeJsonValue(writer, item, allocator);
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

                // Write key
                try writer.writeByte('"');
                for (entry.key_ptr.*) |c| {
                    switch (c) {
                        '"' => try writer.writeAll("\\\""),
                        '\\' => try writer.writeAll("\\\\"),
                        else => try writer.writeByte(c),
                    }
                }
                try writer.writeAll("\":");

                // Write value
                try writeJsonValue(writer, entry.value_ptr.*, allocator);
            }
            try writer.writeByte('}');
        },
    }
}

// ============================================================================
// JSON Write Mode - Passthrough (NDJSON is valid JSON lines)
// ============================================================================

fn writeMode() !void {
    var stdin_buf: [64 * 1024]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [64 * 1024]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    // Passthrough - NDJSON is already valid JSON lines
    while (true) {
        const maybe_line = reader.takeDelimiter('\n') catch |err| {
            std.debug.print("json: read error: {}\n", .{err});
            std.process.exit(1);
        };

        if (maybe_line) |line| {
            try writer.writeAll(line);
            try writer.writeByte('\n');
        } else {
            break;
        }
    }

    try writer.flush();
}

// ============================================================================
// Tests
// ============================================================================

test "manifest output" {
    // Basic smoke test
    var buf: [1024]u8 = undefined;
    var fbs = std.io.fixedBufferStream(&buf);
    const w = fbs.writer();
    try w.writeAll("{\"name\":\"json\"}");
    try std.testing.expect(fbs.getWritten().len > 0);
}
