//! Minimal JN Plugin Example
//!
//! Demonstrates how to use the JN foundation libraries to create a plugin.
//! This is a simple passthrough plugin that reads NDJSON and outputs NDJSON.
//!
//! Build: zig build-exe minimal-plugin.zig -fllvm -O ReleaseFast -femit-bin=minimal
//! Usage:
//!   echo '{"name":"Alice"}' | ./minimal --mode=read
//!   ./minimal --jn-meta

const std = @import("std");

// Import JN libraries
// In a real plugin, these would be imported from the installed libraries.
// For now, we inline the necessary functionality.

// ============================================================================
// Plugin Metadata (from jn-plugin)
// ============================================================================

const Role = enum {
    format,
    protocol,
    compression,
    database,

    pub fn toString(self: Role) []const u8 {
        return switch (self) {
            .format => "format",
            .protocol => "protocol",
            .compression => "compression",
            .database => "database",
        };
    }
};

const Mode = enum {
    read,
    write,
    raw,
    profiles,

    pub fn toString(self: Mode) []const u8 {
        return switch (self) {
            .read => "read",
            .write => "write",
            .raw => "raw",
            .profiles => "profiles",
        };
    }
};

const PluginMeta = struct {
    name: []const u8,
    version: []const u8,
    matches: []const []const u8,
    role: Role,
    modes: []const Mode,
    supports_raw: bool = false,
};

// ============================================================================
// Plugin Definition
// ============================================================================

const plugin_meta = PluginMeta{
    .name = "minimal",
    .version = "0.1.0",
    .matches = &.{".*\\.minimal$"},
    .role = .format,
    .modes = &.{ .read, .write },
};

// ============================================================================
// Main Entry Point
// ============================================================================

pub fn main() !void {
    // Parse arguments
    var args_iter = std.process.args();
    _ = args_iter.skip(); // Skip program name

    var mode: []const u8 = "read";
    var jn_meta = false;

    while (args_iter.next()) |arg| {
        if (std.mem.eql(u8, arg, "--jn-meta")) {
            jn_meta = true;
        } else if (std.mem.startsWith(u8, arg, "--mode=")) {
            mode = arg["--mode=".len..];
        }
    }

    // Handle --jn-meta
    if (jn_meta) {
        try outputManifest();
        return;
    }

    // Dispatch based on mode
    if (std.mem.eql(u8, mode, "read")) {
        try readMode();
    } else if (std.mem.eql(u8, mode, "write")) {
        try writeMode();
    } else {
        std.debug.print("minimal: error: unknown mode '{s}'\n", .{mode});
        std.process.exit(1);
    }
}

// ============================================================================
// Manifest Output (from jn-plugin)
// ============================================================================

fn outputManifest() !void {
    var stdout_buf: [4096]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    try writer.writeAll("{\"name\":\"");
    try writer.writeAll(plugin_meta.name);
    try writer.writeAll("\",\"version\":\"");
    try writer.writeAll(plugin_meta.version);
    try writer.writeAll("\",\"matches\":[");

    for (plugin_meta.matches, 0..) |pattern, i| {
        if (i > 0) try writer.writeByte(',');
        try writer.writeByte('"');
        for (pattern) |c| {
            if (c == '"' or c == '\\') try writer.writeByte('\\');
            try writer.writeByte(c);
        }
        try writer.writeByte('"');
    }

    try writer.writeAll("],\"role\":\"");
    try writer.writeAll(plugin_meta.role.toString());
    try writer.writeAll("\",\"modes\":[");

    for (plugin_meta.modes, 0..) |m, i| {
        if (i > 0) try writer.writeByte(',');
        try writer.writeByte('"');
        try writer.writeAll(m.toString());
        try writer.writeByte('"');
    }

    try writer.writeAll("]}\n");
    try writer.flush();
}

// ============================================================================
// Read Mode - Passthrough (from jn-core patterns)
// ============================================================================

fn readMode() !void {
    var stdin_buf: [64 * 1024]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [64 * 1024]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    // Simple passthrough - read lines, write lines
    while (true) {
        const maybe_line = reader.takeDelimiter('\n') catch |err| {
            std.debug.print("minimal: read error: {}\n", .{err});
            std.process.exit(1);
        };

        if (maybe_line) |line| {
            // Strip CR for Windows compatibility
            const clean_line = if (line.len > 0 and line[line.len - 1] == '\r')
                line[0 .. line.len - 1]
            else
                line;

            if (clean_line.len == 0) continue;

            writer.writeAll(clean_line) catch |err| {
                if (err == error.BrokenPipe) std.process.exit(0);
                return err;
            };
            writer.writeByte('\n') catch |err| {
                if (err == error.BrokenPipe) std.process.exit(0);
                return err;
            };
        } else {
            break;
        }
    }

    writer.flush() catch |err| {
        if (err == error.BrokenPipe) std.process.exit(0);
        // Ignore other flush errors at exit
    };
}

// ============================================================================
// Write Mode - Also passthrough for this minimal example
// ============================================================================

fn writeMode() !void {
    // Same as read mode for this minimal example
    try readMode();
}
