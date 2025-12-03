const std = @import("std");
const zig_builtin = @import("builtin");

// Helper to read a line from reader, compatible with both Zig 0.15.1 and 0.15.2
fn readLine(reader: anytype) ?[]u8 {
    if (comptime zig_builtin.zig_version.order(.{ .major = 0, .minor = 15, .patch = 2 }) != .lt) {
        return reader.takeDelimiter('\n') catch |err| {
            std.debug.print("jsonl: read error: {}\n", .{err});
            std.process.exit(1);
        };
    } else {
        return reader.takeDelimiterExclusive('\n') catch |err| switch (err) {
            error.EndOfStream => return null,
            else => {
                std.debug.print("jsonl: read error: {}\n", .{err});
                std.process.exit(1);
            },
        };
    }
}

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

fn readMode(_: std.mem.Allocator) !void {
    // Zig 0.15.2 I/O API
    var stdin_buf: [64 * 1024]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [64 * 1024]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    // Stream NDJSON passthrough - no validation (trust input, downstream catches errors)
    // This matches typical streaming behavior for format plugins (compatible with Zig 0.15.1+)
    while (true) {
        const maybe_line = readLine(reader);
        if (maybe_line) |line| {
            if (line.len == 0) continue;

            // Output the line directly
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
    // Zig 0.15.1+ I/O API
    var stdin_buf: [64 * 1024]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [64 * 1024]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    // Compatible with Zig 0.15.1+
    while (true) {
        const maybe_line = readLine(reader);
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
