//! Error handling utilities for JN plugins and tools.
//!
//! Provides consistent error messaging and exit handling across all JN components.

const std = @import("std");
const builtin = @import("builtin");

/// Exit the program with an error message to stderr.
///
/// Prints the formatted message to stderr and exits with code 1.
/// Use this for fatal errors that should terminate the plugin.
///
/// Example:
/// ```zig
/// exitWithError("unknown mode: {s}", .{mode});
/// ```
pub fn exitWithError(comptime fmt: []const u8, args: anytype) noreturn {
    std.debug.print(fmt ++ "\n", args);
    std.process.exit(1);
}

/// Exit cleanly (code 0) - typically used for BrokenPipe.
pub fn exitClean() noreturn {
    std.process.exit(0);
}

/// Print a warning message to stderr (non-fatal).
pub fn warn(comptime fmt: []const u8, args: anytype) void {
    std.debug.print("warning: " ++ fmt ++ "\n", args);
}

/// Standard exit codes for JN tools
pub const ExitCode = enum(u8) {
    success = 0,
    general_error = 1,
    usage_error = 2,

    pub fn exit(self: ExitCode) noreturn {
        std.process.exit(@intFromEnum(self));
    }
};

// ============================================================================
// Tests
// ============================================================================

test "ExitCode has expected values" {
    const testing = std.testing;
    try testing.expectEqual(@as(u8, 0), @intFromEnum(ExitCode.success));
    try testing.expectEqual(@as(u8, 1), @intFromEnum(ExitCode.general_error));
    try testing.expectEqual(@as(u8, 2), @intFromEnum(ExitCode.usage_error));
}
