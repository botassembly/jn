const std = @import("std");
const comprezz = @import("comprezz.zig");

pub fn main() !void {
    // Streaming compression test - read from stdin, compress to stdout
    const stdin = std.fs.File.stdin();
    var stdin_buf: [64 * 1024]u8 = undefined;
    var stdin_reader = stdin.reader(&stdin_buf);

    const stdout = std.fs.File.stdout();
    var stdout_buf: [64 * 1024]u8 = undefined;
    var stdout_writer = stdout.writer(&stdout_buf);

    // Compress with default level
    comprezz.compress(&stdin_reader.interface, &stdout_writer.interface, .{}) catch |err| {
        std.debug.print("Compression error: {}\n", .{err});
        std.process.exit(1);
    };

    // Flush output
    stdout_writer.interface.flush() catch |err| {
        std.debug.print("Flush error: {}\n", .{err});
        std.process.exit(1);
    };
}
