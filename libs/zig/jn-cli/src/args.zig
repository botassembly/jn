//! Command line argument parsing for JN plugins.
//!
//! Provides simple argument parsing following the patterns used in
//! existing JN plugins. Supports both --key=value and --flag styles.

const std = @import("std");

/// Maximum number of arguments to track
const MAX_ARGS = 32;

/// Parsed argument storage.
///
/// Stores parsed arguments as key-value pairs where the key is the
/// argument name (without --) and the value is the argument value
/// (or empty string for flags).
pub const ArgParser = struct {
    /// Stored argument keys (without --)
    keys: [MAX_ARGS][]const u8 = undefined,
    /// Stored argument values
    values: [MAX_ARGS][]const u8 = undefined,
    /// Number of stored arguments
    count: usize = 0,

    const Self = @This();

    /// Initialize an empty parser
    pub fn init() Self {
        return Self{};
    }

    /// Add a parsed argument
    fn add(self: *Self, key: []const u8, value: []const u8) void {
        if (self.count < MAX_ARGS) {
            self.keys[self.count] = key;
            self.values[self.count] = value;
            self.count += 1;
        } else {
            // Warn user about truncated arguments - this indicates a bug or
            // unusual usage pattern (most plugins have far fewer than 32 args)
            std.debug.print("Warning: argument '--{s}' ignored (max {d} arguments)\n", .{ key, MAX_ARGS });
        }
    }

    /// Get the value of a named argument.
    ///
    /// Returns the value if the argument was provided, or default if not.
    /// For flags (--flag without =value), returns empty string.
    pub fn get(self: *const Self, name: []const u8, default: ?[]const u8) ?[]const u8 {
        for (0..self.count) |i| {
            if (std.mem.eql(u8, self.keys[i], name)) {
                return self.values[i];
            }
        }
        return default;
    }

    /// Check if a flag is present.
    ///
    /// A flag is an argument like --jn-meta or --help without a value.
    pub fn has(self: *const Self, name: []const u8) bool {
        for (0..self.count) |i| {
            if (std.mem.eql(u8, self.keys[i], name)) {
                return true;
            }
        }
        return false;
    }
};

/// Parse command line arguments into an ArgParser.
///
/// Handles both --key=value and --flag styles.
/// Skips the program name (first argument).
///
/// Example:
/// ```zig
/// const parsed = parseArgs();
/// const mode = parsed.get("mode", "read").?;
/// const jn_meta = parsed.has("jn-meta");
/// ```
pub fn parseArgs() ArgParser {
    var parser = ArgParser.init();

    var args_iter = std.process.args();
    _ = args_iter.skip(); // Skip program name

    while (args_iter.next()) |arg| {
        if (std.mem.startsWith(u8, arg, "--")) {
            const rest = arg[2..];

            // Check for --key=value style
            if (std.mem.indexOf(u8, rest, "=")) |eq_pos| {
                const key = rest[0..eq_pos];
                const value = rest[eq_pos + 1 ..];
                parser.add(key, value);
            } else {
                // Flag style: --flag
                parser.add(rest, "");
            }
        } else if (std.mem.startsWith(u8, arg, "-") and arg.len > 1) {
            // Handle single-dash short options like -r, -s, -c
            // Also handle -n=5 style
            const rest = arg[1..];

            // Check for -k=value style
            if (std.mem.indexOf(u8, rest, "=")) |eq_pos| {
                const key = rest[0..eq_pos];
                const value = rest[eq_pos + 1 ..];
                parser.add(key, value);
            } else {
                // Flag style: -r (single letter flag)
                // Each character is a separate flag
                // Use slices into the original arg string to avoid dangling pointers
                for (0..rest.len) |i| {
                    const key = rest[i .. i + 1];
                    parser.add(key, "");
                }
            }
        }
        // Ignore non-dashed arguments (positional args)
    }

    return parser;
}

/// Get an argument value (convenience wrapper).
pub fn getArg(name: []const u8, default: ?[]const u8) ?[]const u8 {
    const parsed = parseArgs();
    return parsed.get(name, default);
}

/// Check if a flag is present (convenience wrapper).
pub fn hasFlag(name: []const u8) bool {
    const parsed = parseArgs();
    return parsed.has(name);
}

// ============================================================================
// Tests
// ============================================================================

test "ArgParser stores and retrieves arguments" {
    var parser = ArgParser.init();
    parser.add("mode", "read");
    parser.add("delimiter", ",");
    parser.add("jn-meta", "");

    try std.testing.expectEqualStrings("read", parser.get("mode", null).?);
    try std.testing.expectEqualStrings(",", parser.get("delimiter", null).?);
    try std.testing.expect(parser.has("jn-meta"));
    try std.testing.expect(!parser.has("unknown"));
}

test "ArgParser returns default for missing args" {
    const parser = ArgParser.init();

    try std.testing.expectEqualStrings("default", parser.get("missing", "default").?);
    try std.testing.expect(parser.get("missing", null) == null);
}

test "ArgParser handles MAX_ARGS limit" {
    var parser = ArgParser.init();

    // Add MAX_ARGS arguments
    for (0..MAX_ARGS) |i| {
        var key_buf: [32]u8 = undefined;
        const key = std.fmt.bufPrint(&key_buf, "arg{d}", .{i}) catch unreachable;
        parser.add(key, "value");
    }

    try std.testing.expectEqual(@as(usize, MAX_ARGS), parser.count);

    // Attempting to add more should not increase count (truncated)
    parser.add("extra", "value");
    try std.testing.expectEqual(@as(usize, MAX_ARGS), parser.count);

    // The truncated argument should not be accessible
    try std.testing.expect(!parser.has("extra"));
}
