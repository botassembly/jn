//! Plugin manifest output for JN plugins.
//!
//! Provides the standard --jn-meta JSON output that all plugins must support.

const std = @import("std");
const meta = @import("meta.zig");

/// Output the plugin manifest as JSON to the given writer.
///
/// This implements the --jn-meta output format expected by JN for plugin discovery.
///
/// Example output:
/// ```json
/// {"name":"csv","version":"0.1.0","matches":[".*\\.csv$"],"role":"format","modes":["read","write"]}
/// ```
pub fn outputManifest(writer: anytype, plugin: meta.PluginMeta) !void {
    // {"name":"
    try writer.writeAll("{\"name\":\"");
    try writer.writeAll(plugin.name);

    // ","version":"
    try writer.writeAll("\",\"version\":\"");
    try writer.writeAll(plugin.version);

    // ","matches":[
    try writer.writeAll("\",\"matches\":[");
    for (plugin.matches, 0..) |pattern, i| {
        if (i > 0) try writer.writeByte(',');
        try writer.writeByte('"');
        // Escape backslashes and quotes in pattern
        for (pattern) |c| {
            if (c == '"' or c == '\\') try writer.writeByte('\\');
            try writer.writeByte(c);
        }
        try writer.writeByte('"');
    }

    // ],"role":"
    try writer.writeAll("],\"role\":\"");
    try writer.writeAll(plugin.role.toString());

    // ","modes":[
    try writer.writeAll("\",\"modes\":[");
    for (plugin.modes, 0..) |mode, i| {
        if (i > 0) try writer.writeByte(',');
        try writer.writeByte('"');
        try writer.writeAll(mode.toString());
        try writer.writeByte('"');
    }

    // Optional supports_raw
    if (plugin.supports_raw) {
        try writer.writeAll("],\"supports_raw\":true}\n");
    } else {
        try writer.writeAll("]}\n");
    }
}

/// Output manifest to stdout with buffered writing.
///
/// Convenience function for plugins to use in --jn-meta handling.
pub fn outputManifestToStdout(plugin: meta.PluginMeta) !void {
    var stdout_buf: [4096]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    try outputManifest(writer, plugin);
    try writer.flush();
}

// ============================================================================
// Tests
// ============================================================================

test "outputManifest produces valid JSON" {
    const testing = std.testing;

    const test_meta = meta.PluginMeta{
        .name = "test",
        .version = "1.0.0",
        .matches = &.{".*\\.test$"},
        .role = .format,
        .modes = &.{ .read, .write },
    };

    var buf: [1024]u8 = undefined;
    var fbs = std.io.fixedBufferStream(&buf);
    const writer = fbs.writer();

    try outputManifest(writer, test_meta);

    const output = fbs.getWritten();

    // Verify it's valid JSON by checking key parts
    try testing.expect(std.mem.indexOf(u8, output, "\"name\":\"test\"") != null);
    try testing.expect(std.mem.indexOf(u8, output, "\"version\":\"1.0.0\"") != null);
    try testing.expect(std.mem.indexOf(u8, output, "\"role\":\"format\"") != null);
}

test "outputManifest escapes patterns correctly" {
    const testing = std.testing;

    const test_meta = meta.PluginMeta{
        .name = "csv",
        .version = "0.1.0",
        .matches = &.{".*\\.csv$"},
        .role = .format,
        .modes = &.{.read},
    };

    var buf: [1024]u8 = undefined;
    var fbs = std.io.fixedBufferStream(&buf);
    const writer = fbs.writer();

    try outputManifest(writer, test_meta);

    const output = fbs.getWritten();

    // Backslash should be escaped
    try testing.expect(std.mem.indexOf(u8, output, ".*\\\\.csv$") != null);
}
