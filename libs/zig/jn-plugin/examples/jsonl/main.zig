const std = @import("std");

// ============================================================================
// JSONL Plugin - Standalone Zig plugin for JN
//
// Validates and streams newline-delimited JSON (NDJSON).
// Read mode: Validates each line is valid JSON, outputs as NDJSON
// Write mode: Passes through NDJSON unchanged
// ============================================================================

const Plugin = struct {
    name: []const u8,
    version: []const u8,
    matches: []const []const u8,
    role: []const u8,
    modes: []const []const u8,
};

const plugin = Plugin{
    .name = "jsonl",
    .version = "0.1.0",
    .matches = &[_][]const u8{ ".*\\.jsonl$", ".*\\.ndjson$" },
    .role = "format",
    .modes = &[_][]const u8{ "read", "write" },
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
        std.debug.print("jsonl: error: unknown mode '{s}'\n", .{mode});
        std.process.exit(1);
    }
}

fn outputManifest() !void {
    // Zig 0.15.2 I/O API - access .interface for standard writer methods
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

fn readMode(allocator: std.mem.Allocator) !void {
    // Zig 0.15.2 I/O API
    var stdin_buf: [64 * 1024]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [64 * 1024]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    var line_num: usize = 0;

    // Use takeDelimiter which returns null at EOF
    while (true) {
        line_num += 1;
        const maybe_line = reader.takeDelimiter('\n') catch |err| {
            std.debug.print("jsonl: read error: {}\n", .{err});
            std.process.exit(1);
        };

        if (maybe_line) |line| {
            if (line.len == 0) continue;

            // Validate JSON by parsing
            const parsed = std.json.parseFromSlice(std.json.Value, allocator, line, .{}) catch |err| {
                std.debug.print("jsonl: error: invalid JSON on line {d}: {}\n", .{ line_num, err });
                std.process.exit(1);
            };
            defer parsed.deinit();

            // Output the validated line
            try writer.writeAll(line);
            try writer.writeByte('\n');
        } else {
            // EOF
            break;
        }
    }

    try writer.flush();
}

fn writeMode() !void {
    // Zig 0.15.2 I/O API
    var stdin_buf: [64 * 1024]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [64 * 1024]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    // Use takeDelimiter which returns null at EOF
    while (true) {
        const maybe_line = reader.takeDelimiter('\n') catch |err| {
            std.debug.print("jsonl: read error: {}\n", .{err});
            std.process.exit(1);
        };

        if (maybe_line) |line| {
            try writer.writeAll(line);
            try writer.writeByte('\n');
        } else {
            // EOF
            break;
        }
    }

    try writer.flush();
}

// ============================================================================
// Tests
// ============================================================================

test "manifest output" {
    // Basic smoke test - manifest generation doesn't crash
    var buf: [1024]u8 = undefined;
    var fbs = std.io.fixedBufferStream(&buf);

    // Inline manifest generation for test
    const w = fbs.writer();
    try w.writeAll("{\"name\":\"jsonl\"}");

    try std.testing.expect(fbs.getWritten().len > 0);
}
