const std = @import("std");
const comprezz = @import("comprezz.zig");

pub fn main() !void {
    // Test: compress "Hello, World!" and verify output is valid gzip
    const data = "Hello, World! This is a test of gzip compression using comprezz library. Let's add more text to make it compress better with repeated words: test test test test.";

    // Create input reader
    var input_buf: [4096]u8 = undefined;
    @memcpy(input_buf[0..data.len], data);
    var input_reader = std.Io.Reader.fixed(input_buf[0..data.len]);

    // Create output - write directly to stdout for testing
    const stdout = std.fs.File.stdout();
    var stdout_buf: [4096]u8 = undefined;
    var stdout_writer = stdout.writer(&stdout_buf);

    // Compress
    comprezz.compress(&input_reader, &stdout_writer.interface, .{}) catch |err| {
        std.debug.print("Compression error: {}\n", .{err});
        std.process.exit(1);
    };

    // Flush any remaining data
    stdout_writer.interface.flush() catch |err| {
        std.debug.print("Flush error: {}\n", .{err});
        std.process.exit(1);
    };

    std.debug.print("Input: {} bytes\n", .{data.len});
}
