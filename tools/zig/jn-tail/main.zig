//! jn-tail: Output last N records from NDJSON stream
//!
//! Usage:
//!   jn-tail [OPTIONS]
//!
//! Options:
//!   -n, --lines=N           Number of records to output (default: 10)
//!   --help, -h              Show this help
//!   --version               Show version
//!
//! Examples:
//!   cat data.ndjson | jn-tail
//!   cat data.ndjson | jn-tail -n 5
//!   cat data.ndjson | jn-tail --lines=20

const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");

const VERSION = "0.1.0";
const DEFAULT_LINES: usize = 10;
const MAX_LINES: usize = 10000;
/// Maximum total memory for buffered lines (100MB) to prevent OOM
const MAX_TOTAL_MEMORY: usize = 100 * 1024 * 1024;

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

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
            jn_core.exitWithError("jn-tail: invalid number: {s}", .{n_str});
        };
    } else if (args.get("lines", null)) |n_str| {
        n = std.fmt.parseInt(usize, n_str, 10) catch {
            jn_core.exitWithError("jn-tail: invalid number: {s}", .{n_str});
        };
    }

    if (n > MAX_LINES) {
        jn_core.exitWithError("jn-tail: maximum lines is {d}", .{MAX_LINES});
    }

    // Read all lines into circular buffer
    // Initialize to empty slices to avoid undefined behavior if logic has bugs
    var ring_buffer: [MAX_LINES][]u8 = .{&[_]u8{}} ** MAX_LINES;
    var ring_pos: usize = 0;
    var ring_count: usize = 0;
    var total_memory: usize = 0;

    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;

        // Track memory: subtract old line if overwriting
        if (ring_count >= n) {
            total_memory -= ring_buffer[ring_pos].len;
            allocator.free(ring_buffer[ring_pos]);
        }

        // Check memory limit before allocating
        if (total_memory + line.len > MAX_TOTAL_MEMORY) {
            jn_core.exitWithError("jn-tail: memory limit exceeded ({d}MB max)\nHint: use smaller -n value or process fewer records", .{MAX_TOTAL_MEMORY / (1024 * 1024)});
        }

        // Copy line to heap
        const line_copy = allocator.dupe(u8, line) catch {
            jn_core.exitWithError("jn-tail: out of memory", .{});
        };

        ring_buffer[ring_pos] = line_copy;
        total_memory += line.len;
        ring_pos = (ring_pos + 1) % n;
        if (ring_count < n) ring_count += 1;
    }

    // Output buffered lines in order
    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    if (ring_count > 0) {
        const start = if (ring_count < n) 0 else ring_pos;
        var i: usize = 0;
        while (i < ring_count) : (i += 1) {
            const idx = (start + i) % n;
            writer.writeAll(ring_buffer[idx]) catch |err| jn_core.handleWriteError(err);
            writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
            allocator.free(ring_buffer[idx]);
        }
    }

    jn_core.flushWriter(writer);
}

/// Print version
fn printVersion() void {
    var buf: [256]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.print("jn-tail {s}\n", .{VERSION}) catch {};
    jn_core.flushWriter(stdout);
}

/// Print usage information
fn printUsage() void {
    const usage =
        \\jn-tail - Output last N records from NDJSON stream
        \\
        \\Usage: jn-tail [OPTIONS]
        \\
        \\Options:
        \\  -n, --lines=N         Number of records to output (default: 10)
        \\  --help, -h            Show this help
        \\  --version             Show version
        \\
        \\Note: jn-tail buffers up to 10000 lines (max 100MB) in memory.
        \\
        \\Examples:
        \\  cat data.ndjson | jn-tail
        \\  cat data.ndjson | jn-tail -n 5
        \\  cat data.ndjson | jn-tail --lines=20
        \\
    ;
    var buf: [1024]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.writeAll(usage) catch {};
    jn_core.flushWriter(stdout);
}

// Tests
test "default lines is 10" {
    try std.testing.expectEqual(@as(usize, 10), DEFAULT_LINES);
}
