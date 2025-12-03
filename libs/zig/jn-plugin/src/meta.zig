//! Plugin metadata types for JN plugins.
//!
//! Defines the standard metadata structure that all JN plugins must provide.

const std = @import("std");

/// Plugin role - what type of plugin this is
pub const Role = enum {
    format, // Format converter (csv, json, etc.)
    protocol, // Protocol handler (http, s3, etc.)
    compression, // Compression handler (gz, bz2, etc.)
    database, // Database connector (duckdb, etc.)

    pub fn toString(self: Role) []const u8 {
        return switch (self) {
            .format => "format",
            .protocol => "protocol",
            .compression => "compression",
            .database => "database",
        };
    }
};

/// Plugin mode - what operations the plugin supports
pub const Mode = enum {
    read, // Read from source, output NDJSON
    write, // Read NDJSON, write to destination
    raw, // Raw passthrough (e.g., decompression)
    profiles, // Output available profiles

    pub fn toString(self: Mode) []const u8 {
        return switch (self) {
            .read => "read",
            .write => "write",
            .raw => "raw",
            .profiles => "profiles",
        };
    }
};

/// Plugin metadata structure.
///
/// Every JN plugin must define its metadata using this structure.
/// This is used for plugin discovery and manifest output (--jn-meta).
///
/// Example:
/// ```zig
/// const plugin_meta = PluginMeta{
///     .name = "csv",
///     .version = "0.1.0",
///     .matches = &.{ ".*\\.csv$", ".*\\.tsv$" },
///     .role = .format,
///     .modes = &.{ .read, .write },
/// };
/// ```
pub const PluginMeta = struct {
    /// Plugin name (e.g., "csv", "json", "gz")
    name: []const u8,

    /// Plugin version (semver format)
    version: []const u8,

    /// Regex patterns this plugin matches
    matches: []const []const u8,

    /// Plugin role
    role: Role,

    /// Supported modes
    modes: []const Mode,

    /// Whether the plugin supports raw mode (for compression plugins)
    supports_raw: bool = false,
};

// ============================================================================
// Tests
// ============================================================================

test "Role.toString returns correct strings" {
    try std.testing.expectEqualStrings("format", Role.format.toString());
    try std.testing.expectEqualStrings("compression", Role.compression.toString());
}

test "Mode.toString returns correct strings" {
    try std.testing.expectEqualStrings("read", Mode.read.toString());
    try std.testing.expectEqualStrings("write", Mode.write.toString());
}

test "PluginMeta can be constructed" {
    const meta = PluginMeta{
        .name = "test",
        .version = "1.0.0",
        .matches = &.{".*\\.test$"},
        .role = .format,
        .modes = &.{ .read, .write },
    };

    try std.testing.expectEqualStrings("test", meta.name);
    try std.testing.expect(meta.modes.len == 2);
}
