const std = @import("std");

// ============================================================================
// JN Plugin Library for Zig
//
// Provides core types and utilities for building JN plugins in Zig.
// Compatible with Zig 0.15.2 I/O API (Writergate).
// ============================================================================

// ============================================================================
// Core Types
// ============================================================================

pub const Role = enum {
    format,
    filter,
    protocol,

    pub fn toString(self: Role) []const u8 {
        return switch (self) {
            .format => "format",
            .filter => "filter",
            .protocol => "protocol",
        };
    }
};

pub const Mode = enum {
    read,
    write,
    raw,

    pub fn toString(self: Mode) []const u8 {
        return switch (self) {
            .read => "read",
            .write => "write",
            .raw => "raw",
        };
    }

    pub fn fromString(s: []const u8) ?Mode {
        if (std.mem.eql(u8, s, "read")) return .read;
        if (std.mem.eql(u8, s, "write")) return .write;
        if (std.mem.eql(u8, s, "raw")) return .raw;
        return null;
    }
};

pub const Plugin = struct {
    name: []const u8,
    version: []const u8 = "0.1.0",
    matches: []const []const u8,
    role: Role,
    modes: []const Mode,
};

pub const Config = struct {
    mode: Mode,
    args: []const []const u8,
    options: std.StringHashMap([]const u8),
    allocator: std.mem.Allocator,

    pub fn init(allocator: std.mem.Allocator) Config {
        return .{
            .mode = .read,
            .args = &.{},
            .options = std.StringHashMap([]const u8).init(allocator),
            .allocator = allocator,
        };
    }

    pub fn deinit(self: *Config) void {
        self.options.deinit();
    }

    pub fn get(self: *const Config, key: []const u8) ?[]const u8 {
        return self.options.get(key);
    }
};

// ============================================================================
// CLI Argument Parsing
// ============================================================================

pub const ParsedArgs = struct {
    mode: ?Mode = null,
    jn_meta: bool = false,
    positional: std.ArrayList([]const u8),
    options: std.StringHashMap([]const u8),
    allocator: std.mem.Allocator,

    pub fn init(allocator: std.mem.Allocator) ParsedArgs {
        return .{
            .positional = std.ArrayList([]const u8).init(allocator),
            .options = std.StringHashMap([]const u8).init(allocator),
            .allocator = allocator,
        };
    }

    pub fn deinit(self: *ParsedArgs) void {
        self.positional.deinit();
        self.options.deinit();
    }
};

pub fn parseArgs(allocator: std.mem.Allocator) !ParsedArgs {
    var args = ParsedArgs.init(allocator);
    errdefer args.deinit();

    var arg_iter = std.process.args();
    _ = arg_iter.skip(); // Skip program name

    while (arg_iter.next()) |arg| {
        if (std.mem.eql(u8, arg, "--jn-meta")) {
            args.jn_meta = true;
        } else if (std.mem.startsWith(u8, arg, "--mode=")) {
            const value = arg["--mode=".len..];
            args.mode = Mode.fromString(value);
        } else if (std.mem.startsWith(u8, arg, "--")) {
            // Parse --key=value options
            const rest = arg["--".len..];
            if (std.mem.indexOf(u8, rest, "=")) |eq_pos| {
                const key = rest[0..eq_pos];
                const value = rest[eq_pos + 1 ..];
                try args.options.put(key, value);
            }
        } else {
            try args.positional.append(arg);
        }
    }

    return args;
}

// ============================================================================
// Metadata Generation
// ============================================================================

pub fn generateManifest(plugin: Plugin, writer: anytype) !void {
    try writer.writeAll("{\"name\":\"");
    try writer.writeAll(plugin.name);
    try writer.writeAll("\",\"version\":\"");
    try writer.writeAll(plugin.version);
    try writer.writeAll("\",\"matches\":[");

    for (plugin.matches, 0..) |pattern, i| {
        if (i > 0) try writer.writeByte(',');
        try writer.writeByte('"');
        // Escape backslashes in regex patterns
        for (pattern) |c| {
            if (c == '"' or c == '\\') try writer.writeByte('\\');
            try writer.writeByte(c);
        }
        try writer.writeByte('"');
    }

    try writer.writeAll("],\"role\":\"");
    try writer.writeAll(plugin.role.toString());
    try writer.writeAll("\",\"modes\":[");

    for (plugin.modes, 0..) |mode, i| {
        if (i > 0) try writer.writeByte(',');
        try writer.writeByte('"');
        try writer.writeAll(mode.toString());
        try writer.writeByte('"');
    }

    try writer.writeAll("]}\n");
}

// ============================================================================
// Tests
// ============================================================================

test "Mode.fromString" {
    try std.testing.expectEqual(Mode.read, Mode.fromString("read").?);
    try std.testing.expectEqual(Mode.write, Mode.fromString("write").?);
    try std.testing.expectEqual(Mode.raw, Mode.fromString("raw").?);
    try std.testing.expect(Mode.fromString("invalid") == null);
}

test "Role.toString" {
    try std.testing.expectEqualStrings("format", Role.format.toString());
    try std.testing.expectEqualStrings("filter", Role.filter.toString());
    try std.testing.expectEqualStrings("protocol", Role.protocol.toString());
}

test "generateManifest" {
    const plugin = Plugin{
        .name = "test",
        .version = "1.0.0",
        .matches = &[_][]const u8{ ".*\\.json$", ".*\\.jsonl$" },
        .role = .format,
        .modes = &[_]Mode{ .read, .write },
    };

    var buf: [1024]u8 = undefined;
    var fbs = std.io.fixedBufferStream(&buf);
    try generateManifest(plugin, fbs.writer());

    const expected = "{\"name\":\"test\",\"version\":\"1.0.0\",\"matches\":[\".*\\\\.json$\",\".*\\\\.jsonl$\"],\"role\":\"format\",\"modes\":[\"read\",\"write\"]}\n";
    try std.testing.expectEqualStrings(expected, fbs.getWritten());
}
