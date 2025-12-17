//! Buffered stdout writer helpers for JN plugins and tools.
//!
//! Provides writing utilities with proper BrokenPipe handling.
//! Uses the same patterns as existing JN plugins.
//!
//! Thread Safety: These utilities are NOT thread-safe. Each writer instance
//! should be used by a single thread. JN tools are single-threaded by design,
//! using OS pipes for concurrency between processes.
//!
//! ## Design Decision: Exit-on-Error and BrokenPipe Handling
//!
//! This module uses `std.process.exit()` for error handling. This is INTENTIONAL:
//!
//! 1. **Process-per-tool model**: Each JN tool runs as a short-lived subprocess.
//!    Exit codes communicate errors to the orchestrator (see spec/02-architecture.md).
//!
//! 2. **BrokenPipe = success**: When downstream closes the pipe (e.g., `head -n 10`),
//!    SIGPIPE/BrokenPipe occurs. This is NORMAL and signals successful early
//!    termination. Exit code 0 is correct here. See spec/08-streaming-backpressure.md.
//!
//! 3. **OS cleanup**: Process exit reclaims all resources automatically.
//!    No manual cleanup or defer chains needed.
//!
//! 4. **Pipeline efficiency**: Early termination via SIGPIPE allows `head -n 10`
//!    on a 10GB file to process only ~10 records worth of data.
//!
//! See also: spec/08-streaming-backpressure.md ("SIGPIPE and Early Termination")

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
