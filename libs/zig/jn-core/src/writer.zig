//! Buffered stdout writer helpers for JN plugins and tools.
//!
//! Provides writing utilities with proper BrokenPipe handling.
//! Uses the same patterns as existing JN plugins.
//!
//! Thread Safety: These utilities are NOT thread-safe. Each writer instance
//! should be used by a single thread. JN tools are single-threaded by design,
//! using OS pipes for concurrency between processes.

const std = @import("std");

/// Default buffer size for stdout (64KB - same as stdin for consistency)
pub const DEFAULT_BUFFER_SIZE = 64 * 1024;

/// Handle a write error, exiting cleanly on BrokenPipe.
///
/// BrokenPipe means downstream closed the pipe - this is normal
/// behavior (e.g., `jn cat file.csv | head -n 1`).
/// Exit cleanly with code 0 in this case.
///
/// Example:
/// ```zig
/// writer.writeAll(data) catch |err| {
///     handleWriteError(err);
/// };
/// ```
pub fn handleWriteError(err: anyerror) noreturn {
    if (err == error.BrokenPipe) {
        std.process.exit(0);
    }
    std.debug.print("jn-core: write error: {}\n", .{err});
    std.process.exit(1);
}

/// Flush a writer, handling BrokenPipe gracefully.
///
/// Example:
/// ```zig
/// defer flushWriter(&writer);
/// ```
pub fn flushWriter(writer: anytype) void {
    writer.flush() catch |err| {
        if (err == error.BrokenPipe) {
            std.process.exit(0);
        }
        // Ignore other flush errors at exit
    };
}

// ============================================================================
// Tests
// ============================================================================

test "handleWriteError compiles" {
    // Can't really test exit behavior, just verify compilation
    _ = handleWriteError;
}
