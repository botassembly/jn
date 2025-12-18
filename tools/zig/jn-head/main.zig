//! jn-head: Output first N records from NDJSON stream
//!
//! Usage:
//!   jn-head [OPTIONS]
//!
//! Options:
//!   -n, --lines=N           Number of records to output (default: 10)
//!   --help, -h              Show this help
//!   --version               Show version
//!
//! Examples:
//!   cat data.ndjson | jn-head
//!   cat data.ndjson | jn-head -n 5
//!   cat data.ndjson | jn-head --lines=20

const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");

const VERSION = "0.1.0";
const DEFAULT_LINES: usize = 10;

pub fn main() !void {
    const args = jn_cli.parseArgs();

    // Handle --help
    if (args.has("help") or args.has("h")) {
        printUsage();
        return;
    }

    // Handle --version
    if (args.has("version")) {
        printVersion();
        return;
    }

    // Get number of lines
    var n: usize = DEFAULT_LINES;
    if (args.get("n", null)) |n_str| {
        n = std.fmt.parseInt(usize, n_str, 10) catch {
            jn_core.exitWithError("jn-head: invalid number: {s}", .{n_str});
        };
    } else if (args.get("lines", null)) |n_str| {
        n = std.fmt.parseInt(usize, n_str, 10) catch {
            jn_core.exitWithError("jn-head: invalid number: {s}", .{n_str});
        };
    }

    // Stream first N lines
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    var count: usize = 0;
    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;

        writer.writeAll(line) catch |err| jn_core.handleWriteError(err);
        writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);

        count += 1;
        if (count >= n) break;
    }

    jn_core.flushWriter(writer);
}

/// Print version
fn printVersion() void {
    var buf: [256]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.print("jn-head {s}\n", .{VERSION}) catch {};
    jn_core.flushWriter(stdout);
}

/// Print usage information
fn printUsage() void {
    const usage =
        \\jn-head - Output first N records from NDJSON stream
        \\
        \\Usage: jn-head [OPTIONS]
        \\
        \\Options:
        \\  -n, --lines=N         Number of records to output (default: 10)
        \\  --help, -h            Show this help
        \\  --version             Show version
        \\
        \\Examples:
        \\  cat data.ndjson | jn-head
        \\  cat data.ndjson | jn-head -n 5
        \\  cat data.ndjson | jn-head --lines=20
        \\
    ;
    var buf: [1024]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.writeAll(usage) catch {};
    jn_core.flushWriter(stdout);
}

// Tests
test "default lines is 10" {
    try std.testing.expectEqual(@as(usize, 10), DEFAULT_LINES);
}
