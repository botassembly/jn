const std = @import("std");

pub fn main() !void {
    // Use buffered I/O for maximum throughput
    const stdin = std.io.getStdIn();
    const stdout = std.io.getStdOut();

    var buf_reader = std.io.bufferedReader(stdin.reader());
    var buf_writer = std.io.bufferedWriter(stdout.writer());

    const reader = buf_reader.reader();
    const writer = buf_writer.writer();

    // Read line by line, write to stdout
    var line_buf: [65536]u8 = undefined; // 64KB line buffer
    while (true) {
        const line = reader.readUntilDelimiterOrEof(&line_buf, '\n') catch |err| {
            if (err == error.StreamTooLong) {
                // Line too long, skip to next newline
                try reader.skipUntilDelimiterOrEof('\n');
                continue;
            }
            return err;
        } orelse break;

        try writer.writeAll(line);
        try writer.writeByte('\n');
    }

    try buf_writer.flush();
}
