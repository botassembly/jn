//! Buffered stdin reader helpers for JN plugins and tools.
//!
//! Provides line-reading utilities compatible with Zig 0.15.1 and 0.15.2.
//! Uses the same patterns as existing JN plugins.

const std = @import("std");
const builtin = @import("builtin");

/// Default buffer size for stdin (64KB)
pub const DEFAULT_BUFFER_SIZE = 64 * 1024;

/// Possible errors when reading lines
pub const ReadError = error{
    /// End of stream reached (not an error, just EOF)
    EndOfStream,
    /// Input line exceeds buffer capacity
    StreamTooLong,
    /// I/O error during read
    InputOutput,
    /// Read operation was interrupted (can be retried)
    Interrupted,
    /// Connection reset by peer
    ConnectionResetByPeer,
    /// Connection timed out
    ConnectionTimedOut,
    /// Broken pipe
    BrokenPipe,
    /// Not open for reading
    NotOpenForReading,
    /// Unexpected error
    Unexpected,
};

/// Read a line from a buffered reader.
///
/// Compatible with Zig 0.15.1 and 0.15.2 API differences.
/// Returns the line content without the trailing newline, or null at EOF.
/// Strips trailing carriage return (\r) for Windows compatibility.
///
/// WARNING: On read errors (other than EOF), this function prints an error
/// message to stderr and EXITS with code 1. For library usage where you need
/// proper error handling, use `readLineOrError` instead.
///
/// Example:
/// ```zig
/// var stdin_buf: [reader.DEFAULT_BUFFER_SIZE]u8 = undefined;
/// var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
/// const rdr = &stdin_wrapper.interface;
///
/// while (readLine(rdr)) |line| {
///     // process line (does not include newline)
/// }
/// ```
pub fn readLine(reader: anytype) ?[]const u8 {
    const maybe_line = readLineRaw(reader);
    if (maybe_line) |line| {
        return stripCR(line);
    }
    return null;
}

/// Read a line from a buffered reader with proper error handling.
///
/// Unlike `readLine`, this function returns errors instead of exiting,
/// making it suitable for library usage and contexts where graceful
/// error handling is needed.
///
/// Returns:
/// - The line content without trailing newline/CR on success
/// - null at EOF (end of stream)
/// - An error for I/O failures
///
/// Example:
/// ```zig
/// while (true) {
///     const line = readLineOrError(rdr) catch |err| {
///         // Handle error appropriately
///         return err;
///     };
///     if (line == null) break; // EOF
///     // process line
/// }
/// ```
pub fn readLineOrError(reader: anytype) ReadError!?[]const u8 {
    const maybe_line = readLineRawOrError(reader) catch |err| return err;
    if (maybe_line) |line| {
        return stripCR(line);
    }
    return null;
}

/// Read a line without stripping carriage return, with proper error handling.
pub fn readLineRawOrError(reader: anytype) ReadError!?[]u8 {
    // Zig 0.15.2+ uses takeDelimiter, earlier versions use takeDelimiterExclusive
    if (comptime builtin.zig_version.order(.{ .major = 0, .minor = 15, .patch = 2 }) != .lt) {
        return reader.takeDelimiter('\n') catch |err| {
            return mapReaderError(err);
        };
    } else {
        return reader.takeDelimiterExclusive('\n') catch |err| {
            return mapReaderError(err);
        };
    }
}

/// Map reader errors to our ReadError type
fn mapReaderError(err: anyerror) ReadError {
    return switch (err) {
        error.EndOfStream => error.EndOfStream,
        error.StreamTooLong => error.StreamTooLong,
        error.InputOutput => error.InputOutput,
        error.Interrupted => error.Interrupted,
        error.ConnectionResetByPeer => error.ConnectionResetByPeer,
        error.ConnectionTimedOut => error.ConnectionTimedOut,
        error.BrokenPipe => error.BrokenPipe,
        error.NotOpenForReading => error.NotOpenForReading,
        else => error.Unexpected,
    };
}

/// Read a line without stripping carriage return.
/// WARNING: Exits on error. Use `readLineRawOrError` for proper error handling.
pub fn readLineRaw(reader: anytype) ?[]u8 {
    // Zig 0.15.2+ uses takeDelimiter, earlier versions use takeDelimiterExclusive
    if (comptime builtin.zig_version.order(.{ .major = 0, .minor = 15, .patch = 2 }) != .lt) {
        return reader.takeDelimiter('\n') catch |err| {
            std.debug.print("jn-core: read error: {}\n", .{err});
            std.process.exit(1);
        };
    } else {
        return reader.takeDelimiterExclusive('\n') catch |err| switch (err) {
            error.EndOfStream => return null,
            else => {
                std.debug.print("jn-core: read error: {}\n", .{err});
                std.process.exit(1);
            },
        };
    }
}

/// Strip trailing carriage return from a line for Windows compatibility.
pub fn stripCR(line: []const u8) []const u8 {
    if (line.len > 0 and line[line.len - 1] == '\r') {
        return line[0 .. line.len - 1];
    }
    return line;
}

// ============================================================================
// Tests
// ============================================================================

test "stripCR removes carriage return" {
    const testing = std.testing;
    try testing.expectEqualStrings("hello", stripCR("hello\r"));
    try testing.expectEqualStrings("hello", stripCR("hello"));
    try testing.expectEqualStrings("", stripCR("\r"));
    try testing.expectEqualStrings("", stripCR(""));
}
